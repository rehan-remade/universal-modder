// REFERENCE ONLY - not part of the FalArsenal build. It sits outside the mod folder on purpose
// (tModLoader compiles every .cs file under a mod's folder) and doesn't need to compile as-is.
//
// The agent bridge from the project this example came from: a JSON-lines socket that let an outside
// agent (an LLM with tools, or a trained policy) read the screen as text, click through the menus and
// play, from the title screen on. Enabled by setting AGENT_BRIDGE_PORT (e.g. 7878) before launch.
//
//   {"cmd":"observe"}                        -> the screen as text: menu options (id + label) or world state
//   {"cmd":"click","id":3}                   -> click option 3 from the last observe
//   {"cmd":"type","text":"Bob"}              -> fill the on-screen text box (character / world names)
//   {"cmd":"controls","move":-1,"jump":true,"fire":true,"aim":1.57}   (aim: radians, 0 = right, +y down)
//   {"cmd":"use_item","slot":1}              -> select a hotbar slot and use it once
//   {"cmd":"step", ...controls}              -> controls + observe in one round trip (the 60 Hz loop)
//
// What made it work:
// - Every request is handled on the game's main thread right after an update (a hook on
//   Main.DoUpdate), so each reply describes one consistent frame.
// - Menus are read generically from the UI tree (any element with a click handler) rather than from
//   screen positions, so the agent sees what a player sees. Character and world creation wire their
//   buttons to OnLeftMouseDown, not OnLeftClick, so check both; list rows (play / favorite / ...) only
//   label themselves on mouse-over; the title menu is drawn immediate-mode (no UI tree) and has to be
//   mirrored by hand. Destructive buttons (delete, cloud moves) are left out.
// - Aim by writing Main.mouseX/Y every frame (the game turns and aims from the cursor), and clear
//   delayUseItem so item use works while the window isn't focused.

using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.Audio;
using Terraria.GameContent.UI.Elements;
using Terraria.GameContent.UI.States;
using Terraria.ID;
using Terraria.Localization;
using Terraria.ModLoader;
using Terraria.UI;

namespace YourMod
{
	public class AgentBridge : ModSystem
	{
		public static int Port => int.TryParse(Environment.GetEnvironmentVariable("AGENT_BRIDGE_PORT"), out var p) ? p : 0;
		public static bool Enabled => Port > 0;
		static TcpListener listener;
		static readonly ConcurrentQueue<(string line, TaskCompletionSource<string> reply)> inbox = new();
		static readonly List<(string label, Action click)> options = new();
		// menus use either event: UICharacterCreation / UIWorldCreation wire everything to OnLeftMouseDown
		static readonly FieldInfo clickField = typeof(UIElement).GetField("OnLeftClick", BindingFlags.Instance | BindingFlags.NonPublic);
		static readonly FieldInfo downField = typeof(UIElement).GetField("OnLeftMouseDown", BindingFlags.Instance | BindingFlags.NonPublic);

		public override void Load()
		{
			if (Main.dedServ || !Enabled) return;
			listener = new TcpListener(IPAddress.Loopback, Port);
			listener.Start();
			new Thread(AcceptLoop) { IsBackground = true, Name = "AgentBridge" }.Start();
			On_Main.DoUpdate += AfterUpdate;
			Mod.Logger.Info($"agent bridge listening on 127.0.0.1:{Port}");
		}

		public override void Unload()
		{
			On_Main.DoUpdate -= AfterUpdate;
			listener?.Stop();
			listener = null;
		}

		static void AcceptLoop()
		{
			while (listener != null)
			{
				TcpClient c;
				try { c = listener.AcceptTcpClient(); } catch { return; }
				c.NoDelay = true;
				new Thread(() => Serve(c)) { IsBackground = true }.Start();
			}
		}

		static void Serve(TcpClient c)
		{
			using var s = c.GetStream();
			using var r = new StreamReader(s, Encoding.UTF8);
			using var w = new StreamWriter(s, new UTF8Encoding(false)) { AutoFlush = true };
			try
			{
				string line;
				while ((line = r.ReadLine()) != null)
				{
					// a web page can POST to this port, but its request opens with an HTTP line: hang up before the body runs
					if (!line.StartsWith('{')) return;
					var tcs = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
					inbox.Enqueue((line, tcs));
					w.WriteLine(tcs.Task.Result); // answered on the main thread, after the next update
				}
			}
			catch (IOException) { }
		}

		static void AfterUpdate(On_Main.orig_DoUpdate orig, Main self, ref GameTime gameTime)
		{
			orig(self, ref gameTime);
			while (inbox.TryDequeue(out var job))
			{
				string reply;
				try { reply = Handle(JsonDocument.Parse(job.line).RootElement); }
				catch (Exception e) { reply = JsonSerializer.Serialize(new { error = e.GetType().Name + ": " + e.Message }); }
				job.reply.SetResult(reply);
			}
		}

		static string Handle(JsonElement req)
		{
			string cmd = req.GetProperty("cmd").GetString();
			switch (cmd)
			{
				case "observe":
					return JsonSerializer.Serialize(Observe());
				case "click":
				{
					int id = req.GetProperty("id").GetInt32();
					if (id < 0 || id >= options.Count) return Err($"no option {id}; observe first");
					var (label, click) = options[id];
					click();
					return JsonSerializer.Serialize(new { ok = true, clicked = label });
				}
				case "type":
				{
					if (Main.MenuUI.CurrentState is not UIVirtualKeyboard kb) return Err("no text box on screen");
					kb.Text = req.GetProperty("text").GetString();
					return JsonSerializer.Serialize(new { ok = true, text = kb.Text });
				}
				case "controls":
					AgentBridgePlayer.Set(req);
					return "{\"ok\":true}";
				case "step": // controls for the coming frames + the state after this update, in one round trip
					AgentBridgePlayer.Set(req);
					return JsonSerializer.Serialize(Observe());
				case "use_item":
					AgentBridgePlayer.UseItem(req.GetProperty("slot").GetInt32());
					return "{\"ok\":true}";
				default:
					return Err("unknown cmd " + cmd);
			}
		}

		static string Err(string m) => JsonSerializer.Serialize(new { error = m });

		// ---------------------------------------------------------------- observation

		static object Observe()
		{
			options.Clear();
			if (!Main.gameMenu)
				return new { screen = "in_world", world = WorldState() };
			if (Main.menuMode == 0)
			{
				// the title menu is drawn immediate-mode (no UI tree): mirror its entries (Main.DrawMenu)
				options.Add((Lang.menu[12].Value, () =>
				{
					SoundEngine.PlaySound(SoundID.MenuOpen);
					typeof(Main).GetMethod("ClearPendingPlayerSelectCallbacks", BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public)?.Invoke(null, null);
					Main.menuMode = 1;
					typeof(Main).GetMethod("PrepareLoadedModsAndConfigsForSingleplayer", BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public)?.Invoke(null, null);
				}));
				return new { screen = "title_menu", options = Labels() };
			}
			var state = Main.MenuUI?.CurrentState;
			if (Main.menuMode == 888 && state != null)
			{
				Collect(state, state is UIVirtualKeyboard);
				string title = state.GetType().Name;
				object textBox = state is UIVirtualKeyboard kb ? new { current_text = kb.Text } : null;
				return new { screen = title, options = Labels(), text_box = textBox };
			}
			return new { screen = "busy", menu_mode = Main.menuMode, status = Main.statusText };
		}

		static object[] Labels() => options.Select((o, i) => (object)new { id = i, label = o.label }).ToArray();

		static void Collect(UIElement e, bool keyboard)
		{
			if (clickField?.GetValue(e) != null || downField?.GetValue(e) != null)
			{
				string label = Label(e);
				bool hide = label == null || label == "UIHoverImage"
					|| label.Contains(Language.GetTextValue("UI.Delete"), StringComparison.OrdinalIgnoreCase)
					|| label.StartsWith(Language.GetTextValue("UI.MoveToCloud")) || label.StartsWith(Language.GetTextValue("UI.MoveOffCloud"))
					|| (keyboard && e is UITextPanel<object>); // the 50 on-screen keys: use "type" instead
				if (!hide)
				{
					var el = e;
					options.Add((label, () =>
					{
						// a full click, as the UI would see it
						var evt = new UIMouseEvent(el, el.GetDimensions().Center());
						el.LeftMouseDown(evt);
						el.LeftMouseUp(evt);
						el.LeftClick(evt);
					}));
				}
			}
			foreach (var child in e.Children.ToArray()) Collect(child, keyboard);
		}

		static string Label(UIElement e)
		{
			string own = e switch
			{
				UITextPanel<LocalizedText> t => t.Text,
				UITextPanel<string> t => t.Text,
				UITextPanel<object> t => t.Text,
				UIText t => t.Text,
				_ => null,
			};
			if (!string.IsNullOrWhiteSpace(own)) return own;
			// list-entry buttons (play / favorite / rename ...) only label themselves on mouse-over
			var parent = e.Parent;
			var labelField = parent?.GetType().GetField("_buttonLabel", BindingFlags.Instance | BindingFlags.NonPublic);
			if (labelField != null)
			{
				var evt = new UIMouseEvent(e, e.GetDimensions().Center());
				e.MouseOver(evt);
				string hover = (labelField.GetValue(parent) as UIText)?.Text;
				e.MouseOut(evt);
				string owner = parent switch
				{
					UICharacterListItem c => "character \"" + c.Data.Name + "\"",
					UIWorldListItem w => "world \"" + WorldName(w) + "\"",
					_ => parent.GetType().Name,
				};
				return string.IsNullOrWhiteSpace(hover) ? null : $"{hover}: {owner}";
			}
			if (e is UIColoredImageButton && e.Parent != null && Main.MenuUI.CurrentState is UICharacterCreation)
				return "cosmetic: character appearance category (optional)";
			var title = e.GetType().GetField("_title", BindingFlags.Instance | BindingFlags.NonPublic)?.GetValue(e) as UIText;
			if (title != null) return title.Text;
			var text = e.Children.OfType<UIText>().FirstOrDefault();
			if (text != null && !string.IsNullOrWhiteSpace(text.Text)) return text.Text;
			return e.GetType().Name;
		}

		static string WorldName(UIWorldListItem w) =>
			(typeof(UIWorldListItem).GetField("_data", BindingFlags.Instance | BindingFlags.NonPublic)?.GetValue(w) as Terraria.IO.WorldFileData)?.Name ?? "?";

		static object WorldState()
		{
			var p = Main.LocalPlayer;
			double t = Main.time;
			double hours = Main.dayTime ? 4.5 + t / 3600.0 : 19.5 + t / 3600.0;
			hours %= 24;
			string clock = $"{((int)hours + 11) % 12 + 1}:{(int)((hours % 1) * 60):00} {(hours >= 12 ? "PM" : "AM")}";
			var hotbar = Enumerable.Range(0, 10).Select(i => new { slot = i, name = p.inventory[i].IsAir ? "" : p.inventory[i].Name, stack = p.inventory[i].stack }).ToArray();
			// hostile NPCs, bosses first, then nearest (Main.ActiveNPCs is a ref struct: no LINQ on it)
			var npcs = Main.npc.Take(Main.maxNPCs)
				.Where(n => n.active && !n.friendly && !n.townNPC && n.lifeMax > 5)
				.OrderByDescending(n => n.boss).ThenBy(n => Vector2.DistanceSquared(n.Center, p.Center)).Take(12)
				.Select(n => new { name = n.TypeName, type = n.type, boss = n.boss, x = n.position.X, y = n.position.Y, vx = n.velocity.X, vy = n.velocity.Y, w = n.width, h = n.height, life = n.life, life_max = n.lifeMax, ai = n.ai })
				.ToArray();
			// newest first (RemadeChatMonitor keeps them in a private list)
			var msgs = Main.chatMonitor?.GetType().GetField("_messages", BindingFlags.Instance | BindingFlags.NonPublic)?.GetValue(Main.chatMonitor) as System.Collections.IList;
			var chat = new List<string>();
			if (msgs != null)
				foreach (var m in msgs.Cast<Terraria.UI.Chat.ChatMessageContainer>().Take(6)) chat.Add(m.OriginalText);
			return new
			{
				frame = Main.GameUpdateCount,
				clock,
				night = !Main.dayTime,
				player = new
				{
					x = p.position.X, y = p.position.Y, vx = p.velocity.X, vy = p.velocity.Y, w = p.width, h = p.height,
					life = p.statLife, life_max = p.statLifeMax2, defense = (int)p.statDefense, immune = p.immuneTime, dead = p.dead,
					grounded = p.velocity.Y == 0, selected = p.selectedItem,
				},
				hotbar,
				ammo = p.inventory.Skip(54).Take(4).Where(i => !i.IsAir).Select(i => new { name = i.Name, stack = i.stack }).ToArray(),
				npcs,
				chat,
			};
		}
	}

	/// <summary>Applies the bridge's controls every frame (the agent's reflex layer streams them).</summary>
	public class AgentBridgePlayer : ModPlayer
	{
		static int move; static bool jump, fire; static float aim; static int useSlot = -1, useFrames;

		public static void Set(JsonElement r)
		{
			move = r.TryGetProperty("move", out var m) ? Math.Sign(m.GetInt32()) : 0;
			jump = r.TryGetProperty("jump", out var j) && j.GetBoolean();
			fire = r.TryGetProperty("fire", out var f) && f.GetBoolean();
			if (r.TryGetProperty("aim", out var a)) aim = (float)a.GetDouble();
		}

		public static void UseItem(int slot) { useSlot = slot; useFrames = 4; }

		public override void SetControls()
		{
			if (!AgentBridge.Enabled || Player.whoAmI != Main.myPlayer || Main.gameMenu) return;
			Player.controlLeft = move < 0;
			Player.controlRight = move > 0;
			Player.controlJump = jump;
			Player.controlDown = Player.controlUp = Player.controlHook = Player.controlMount = false;
			if (useFrames > 0)
			{
				Player.selectedItem = useSlot;
				Player.controlUseItem = useFrames-- > 1;
			}
			else
			{
				Player.selectedItem = 0;
				Player.controlUseItem = fire;
			}
			// the game aims (and turns the player) from the cursor
			var at = Player.Center + new Vector2(MathF.Cos(aim), MathF.Sin(aim)) * 200 - Main.screenPosition;
			Main.mouseX = (int)at.X; Main.mouseY = (int)at.Y;
		}

		// no "wait for the mouse button to be released first" between uses while the window is unfocused
		public override bool PreItemCheck() { if (AgentBridge.Enabled) Player.delayUseItem = false; return true; }

		public override void ModifyShootStats(Item item, ref Vector2 position, ref Vector2 velocity, ref int type, ref int damage, ref float knockback)
		{
			if (!AgentBridge.Enabled) return;
			velocity = new Vector2(MathF.Cos(aim), MathF.Sin(aim)) * velocity.Length();
			position = Player.Center;
		}
	}
}
