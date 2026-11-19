using System.Collections.Generic;
using System.Reflection;
using System.Threading;
using HarmonyLib;
using OWML.Common;
using OWML.ModHelper;
using UnityEngine;

namespace BlockCraft;

public class BlockCraftMod : ModBehaviour
{
	public static BlockCraftMod Instance;

	/// <summary>Where this mod is installed, for the dev bridge's command/log/screenshot files.</summary>
	public string ModFolder;

	public string EquipKey = "6";
	public float BlockSize = 1f;
	public int MaxBlocks = 1000;

	private void Awake()
	{
		Instance = this;
		_mainThreadId = Thread.CurrentThread.ManagedThreadId;
	}

	/// <summary>Publish messages queued by other threads (see <see cref="LogRaw"/>).</summary>
	private void Update()
	{
		DrainLogs();
	}

	private void Start()
	{
		Configure(ModHelper.Config);
		ModFolder = ModHelper.Manifest.ModFolderPath;
		new Harmony("SvenTheRedPanda.BlockCraft").PatchAll(Assembly.GetExecutingAssembly());
		LoadManager.OnCompleteSceneLoad += OnCompleteSceneLoad;
		if (LoadManager.GetCurrentScene() == OWScene.SolarSystem)
			OnCompleteSceneLoad(OWScene.TitleScreen, OWScene.SolarSystem);
		Log("BlockCraft loaded", MessageType.Success);
	}

	public override void Configure(IModConfig config)
	{
		EquipKey = config.GetSettingsValue<string>("equipKey");
		BlockSize = config.GetSettingsValue<float>("blockSize");
		MaxBlocks = Mathf.RoundToInt(config.GetSettingsValue<float>("maxBlocks"));
	}

	private void OnCompleteSceneLoad(OWScene previous, OWScene scene)
	{
		if (scene != OWScene.SolarSystem)
			return;
		// Wait one frame so Locator has the player, camera and tool swapper.
		ModHelper.Events.Unity.FireOnNextUpdate(() =>
		{
			BlockTool.Create();
			Log("block tool added to the loop");
			StartPassthrough();
		});
	}

	/// <summary>
	/// Bring up the live passthrough: the guest link, the compositor that paints Minecraft's picture, and
	/// the bridge that keeps the guest's camera on Outer Wilds'.
	/// </summary>
	private void StartPassthrough()
	{
		if (_link != null)
			return;
		_link = new HostLink();
		_link.Start();
		var compositor = Compositor.Create(_link);
		HostBridge.Create(_link, compositor);
		// Its own object, marked to survive the load, exactly like the compositor and the bridge above.
		// Adding it to the mod's own GameObject instead made its Update() run twice and then stop: OWML's
		// object belongs to the loading scene, so the component died with it while the two new objects lived.
		var devGo = new GameObject("BlockCraftDev");
		DontDestroyOnLoad(devGo);
		var dev = devGo.AddComponent<DevBridge>();
		Log($"passthrough up: link on 127.0.0.1:{HostLink.Port}, compositor, bridge, dev {(dev.enabled ? "on" : "off")}",
			MessageType.Success);
	}

	private void OnDestroy()
	{
		_link?.Dispose();
		_link = null;
	}

	private HostLink _link;

	public static void Log(string msg, MessageType type = MessageType.Message)
	{
		LogRaw(msg, type);
	}

	/// <summary>
	/// Write a message the game itself should not see on repeat, and only when it changes.
	///
	/// <p>The link retries once a second while no guest is attached, so logging every failure floods the
	/// console with "Connection refused" and the game visibly stalls doing it.
	/// </summary>
	public static void LogQuiet(string msg, MessageType type = MessageType.Message)
	{
		if (msg == _lastQuiet) return;
		_lastQuiet = msg;
		LogRaw(msg, type);
	}

	/// <summary>
	/// The single place that touches the OWML console.
	///
	/// <p>Callers are not all on the main thread: the link's socket thread and the compositor's render
	/// callbacks both log. OWML's console is a Unity object, so writing to it from another thread is a
	/// data race, and on this machine it wedged the game hard enough to need a restart. Every message is
	/// therefore queued and drained on the main thread, the same way the compositor's frames are.
	/// </summary>
	private static void LogRaw(string msg, MessageType type)
	{
		if (Instance == null || Instance.ModHelper == null)
		{
			Debug.Log("[BlockCraft] " + msg);
			return;
		}

		bool mainThread = Instance._mainThreadId == Thread.CurrentThread.ManagedThreadId;
		if (mainThread)
		{
			Instance.ModHelper.Console.WriteLine(msg, type);
			return;
		}

		lock (Instance._pendingLogs)
		{
			// Bound the queue: a stalled main thread must not turn a log storm into unbounded memory.
			if (Instance._pendingLogs.Count < 256)
				Instance._pendingLogs.Enqueue((msg, type));
		}
	}

	private static string _lastQuiet;

	/// <summary>Forget the last quiet message, so the next failure is reported again.</summary>
	public static void LogResetQuiet() => _lastQuiet = null;

	private readonly Queue<(string Msg, MessageType Type)> _pendingLogs = new();
	private int _mainThreadId;

	/// <summary>Drain messages queued by other threads. Called once per frame on the main thread.</summary>
	internal static void DrainLogs()
	{
		if (Instance == null) return;
		while (true)
		{
			(string Msg, MessageType Type) item;
			lock (Instance._pendingLogs)
			{
				if (Instance._pendingLogs.Count == 0) return;
				item = Instance._pendingLogs.Dequeue();
			}

			Instance.ModHelper.Console.WriteLine(item.Msg, item.Type);
		}
	}
}

[HarmonyPatch(typeof(ToolModeSwapper), "Update")]
internal static class ToolModeSwapperUpdatePatch
{
	// Runs before the swapper reads the tool buttons, so right mouse doesn't also take out the scout launcher.
	private static void Prefix() => BlockTool.Instance?.ConsumeGameToolInput();
}

[HarmonyPatch(typeof(ReferenceFrameTracker), "UpdateTargeting")]
internal static class LockOnPatch
{
	// Left mouse is lock-on; with the block tool out it breaks blocks instead.
	private static void Prefix()
	{
		if (BlockTool.Instance != null && BlockTool.Instance.Equipped && OWInput.IsInputMode(InputMode.Character))
			InputLibrary.lockOn.ConsumeInput();
	}
}
