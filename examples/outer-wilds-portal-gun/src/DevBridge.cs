using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

namespace OWPortalGun;

/// <summary>
/// Test oracle for agents and developers. Off unless `dev.enabled` exists in the mod folder.
/// Write lines to `dev_commands.txt`; they run in order (`wait 2` pauses) and results go to `dev_log.txt`.
/// </summary>
public class DevBridge : MonoBehaviour
{
	private static string s_logPath;
	private string _cmdPath;
	private readonly Queue<string> _queue = new();
	private bool _running;
	private static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

	private void Start()
	{
		var folder = PortalGunMod.Instance.ModFolder;
		if (!File.Exists(Path.Combine(folder, "dev.enabled")))
		{
			enabled = false;
			return;
		}
		_cmdPath = Path.Combine(folder, "dev_commands.txt");
		s_logPath = Path.Combine(folder, "dev_log.txt");
		Directory.CreateDirectory(Path.Combine(folder, "shots"));
		Append("dev bridge on");
	}

	public static void Append(string line)
	{
		if (s_logPath == null) return;
		try
		{
			File.AppendAllText(s_logPath, $"[{DateTime.Now:HH:mm:ss.fff} f{Time.frameCount}] {line}\n");
		}
		catch (IOException) { }
	}

	private void Update()
	{
		if (File.Exists(_cmdPath))
		{
			try
			{
				foreach (var l in File.ReadAllLines(_cmdPath))
					if (!string.IsNullOrWhiteSpace(l) && !l.TrimStart().StartsWith("#"))
						_queue.Enqueue(l.Trim());
				File.Delete(_cmdPath);
			}
			catch (IOException) { }
		}
		if (!_running && _queue.Count > 0)
			StartCoroutine(Run());
	}

	private IEnumerator Run()
	{
		_running = true;
		while (_queue.Count > 0)
		{
			var line = _queue.Dequeue();
			var a = line.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
			Append("> " + line);
			if (a[0] == "wait")
			{
				yield return new WaitForSecondsRealtime(F(a, 1, 1f));
				continue;
			}
			if (a[0] == "walk")
			{
				// walk <seconds> <speed m/s>: drive the player forward along the ground, like holding W
				var until = Time.time + F(a, 1, 1f);
				var speed = F(a, 2, 4f);
				while (Time.time < until)
				{
					yield return new WaitForFixedUpdate();
					var body = Locator.GetPlayerBody();
					var ctrl = Locator.GetPlayerController();
					var ground = ctrl != null && ctrl.IsGrounded() ? ctrl.GetGroundBody() : null;
					if (ground == null)
						continue; // like the real controls: no push while airborne
					var up = body.transform.up;
					var baseVel = ground.GetPointVelocity(body.GetPosition());
					var rel = body.GetVelocity() - baseVel;
					var fwd = Vector3.ProjectOnPlane(Locator.GetPlayerCamera().transform.forward, up).normalized;
					body.SetVelocity(baseVel + fwd * speed + Vector3.Project(rel, up));
				}
				continue;
			}
			if (a[0] == "trace")
			{
				// trace <seconds>: runs alongside the next commands
				StartCoroutine(Trace(F(a, 1, 2f)));
				continue;
			}
			if (a[0] == "waitfor")
			{
				var t = Time.realtimeSinceStartup + F(a, 2, 60f);
				while (!Condition(a[1]) && Time.realtimeSinceStartup < t)
					yield return null;
				Append($"waitfor {a[1]}: {Condition(a[1])}");
				continue;
			}
			try
			{
				Exec(a);
			}
			catch (Exception e)
			{
				Append("ERROR " + e);
			}
			yield return null;
		}
		_running = false;
	}

	private static float F(string[] a, int i, float def) => a.Length > i ? float.Parse(a[i], Inv) : def;

	private static bool Condition(string what)
	{
		switch (what)
		{
			case "solarsystem": return LoadManager.GetCurrentScene() == OWScene.SolarSystem && PortalGun.Instance != null && !LoadManager.IsBusy();
			case "title": return LoadManager.GetCurrentScene() == OWScene.TitleScreen && !LoadManager.IsBusy();
			case "control": return OWInput.IsInputMode(InputMode.Character);
			case "wakeready":
			{
				var fx = Locator.GetPlayerCamera()?.GetComponent<PlayerCameraEffectController>();
				return fx != null && LateInitializerManager.isDoneInitializing
					&& (bool)HarmonyLib.AccessTools.Field(typeof(PlayerCameraEffectController), "_waitForWakeInput").GetValue(fx);
			}
			case "profiles": return LoadManager.GetCurrentScene() == OWScene.TitleScreen && StandaloneProfileManager.SharedInstance.isInitialized
				&& UnityEngine.Object.FindObjectOfType<TitleScreenManager>() != null;
			default: return false;
		}
	}

	private void Exec(string[] a)
	{
		var gun = PortalGun.Instance;
		var cam = Locator.GetPlayerCamera();
		switch (a[0])
		{
			case "profile":
			{
				var pm = StandaloneProfileManager.SharedInstance;
				var exists = false;
				foreach (var pr in pm.profiles)
					if (pr.profileName == a[1]) exists = true;
				var ok = exists ? pm.SwitchProfile(a[1]) : pm.TryCreateProfile(a[1]);
				Append($"{(exists ? "switch to" : "create")} profile {a[1]}: {ok}, current {pm.currentProfile?.profileName}, loops {pm.currentProfileGameSave?.loopCount}");
				break;
			}
			case "resume":
			{
				var title = UnityEngine.Object.FindObjectOfType<TitleScreenManager>();
				// private field: Mono checks field access at JIT time even against publicized references
				var action = HarmonyLib.AccessTools.Field(typeof(TitleScreenManager), "_resumeGameAction").GetValue(title);
				// On a save with one loop the resume button is hidden and has no scene; give it the game scene.
				// (Never the new-game action: it resets the save.) ConfirmSubmit skips the "are you sure?" popup.
				((SubmitActionLoadScene)action).SetSceneToLoad(SubmitActionLoadScene.LoadableScenes.GAME);
				HarmonyLib.AccessTools.Method(typeof(SubmitActionLoadScene), "ConfirmSubmit").Invoke(action, null);
				// The hidden button's Update normally finishes the transition; do it here instead.
				StartCoroutine(FinishLoad());
				Append("resume submitted");
				break;
			}
			case "contacts":
			{
				// colliders touching the player's capsule (inflated a little)
				var body = Locator.GetPlayerBody();
				var capsule = body.GetComponentInChildren<CapsuleCollider>();
				var t = capsule.transform;
				var half = Mathf.Max(0f, capsule.height * 0.5f - capsule.radius);
				var axis = capsule.direction == 0 ? t.right : capsule.direction == 2 ? t.forward : t.up;
				var c = t.TransformPoint(capsule.center);
				var hits = Physics.OverlapCapsule(c - axis * half, c + axis * half, capsule.radius + 0.15f, ~0, QueryTriggerInteraction.Ignore);
				var sb = new StringBuilder($"contacts r={capsule.radius} h={capsule.height}:");
				foreach (var h in hits)
					if (h.attachedRigidbody != body.GetRigidbody())
						sb.Append($" [{h.name} layer {LayerMask.LayerToName(h.gameObject.layer)} parent {h.transform.parent?.name} enabled {h.enabled}]");
				Append(sb.ToString());
				break;
			}
			case "skyscan":
			{
				// skyscan <radius>: ground spots with open sky above (for dropping the ship), relative to the camera
				var radius = F(a, 1, 60f);
				var body = Locator.GetPlayerBody();
				var up = body.transform.up;
				var fwd = Vector3.ProjectOnPlane(cam.transform.forward, up).normalized;
				var right = Vector3.Cross(up, fwd);
				var sb = new StringBuilder("skyscan (right, forward, ground dz, clear):");
				var found = 0;
				for (var x = -radius; x <= radius; x += 8f)
					for (var z = -radius; z <= radius; z += 8f)
					{
						var top = cam.transform.position + right * x + fwd * z + up * 120f;
						if (!Physics.Raycast(top, -up, out var hit, 240f, OWLayerMask.physicalMask, QueryTriggerInteraction.Ignore))
							continue;
						if (Vector3.Dot(hit.normal, up) < 0.9f)
							continue;
						// clear column of radius 6 m from 5 m above the ground up to 60 m
						if (Physics.SphereCast(hit.point + up * 61f, 6f, -up, out var block, 50f, OWLayerMask.physicalMask, QueryTriggerInteraction.Ignore))
							continue;
						var dz = Vector3.Dot(hit.point - cam.transform.position, up);
						sb.Append($" ({x:F0},{z:F0},{dz:F1})");
						found++;
					}
				sb.Append($" found {found}");
				Append(sb.ToString());
				break;
			}
			case "reload":
				// What the end of a loop does (Flashback -> ReloadSceneAsync)
				LoadManager.ReloadSceneAsync(true);
				break;
			case "face":
			{
				// face <0|1> [height offset]: turn the player and camera to look at a portal's centre
				var p = PortalSystem.Instance.Portals[int.Parse(a[1])];
				var body = Locator.GetPlayerBody();
				var target = p.transform.position + p.transform.up * F(a, 2, 0f);
				var dir = target - cam.transform.position;
				var up = body.transform.up;
				var flat = Vector3.ProjectOnPlane(dir, up);
				body.SetRotation(Quaternion.LookRotation(flat.normalized, up));
				Locator.GetPlayerCameraController().SetDegreesY(90f - Vector3.Angle(up, dir));
				break;
			}
			case "wake":
			{
				// Same steps PlayerCameraEffectController runs when the "Wake up" prompt is answered.
				var fx = cam != null ? cam.GetComponent<PlayerCameraEffectController>() : null;
				if (fx == null)
				{
					Append("no player camera yet");
					break;
				}
				var waiting = HarmonyLib.AccessTools.Field(typeof(PlayerCameraEffectController), "_waitForWakeInput");
				if (!(bool)waiting.GetValue(fx))
				{
					Append("not waiting for wake input");
					break;
				}
				waiting.SetValue(fx, false);
				LateInitializerManager.pauseOnInitialization = false;
				Locator.GetPauseCommandListener().RemovePauseCommandLock();
				Locator.GetPromptManager().RemoveScreenPrompt((ScreenPrompt)HarmonyLib.AccessTools.Field(typeof(PlayerCameraEffectController), "_wakePrompt").GetValue(fx));
				OWTime.Unpause(OWTime.PauseType.Sleeping);
				HarmonyLib.AccessTools.Method(typeof(PlayerCameraEffectController), "WakeUp").Invoke(fx, null);
				Append("woke up");
				break;
			}
			case "start":
				LoadManager.LoadSceneAsync(OWScene.SolarSystem, true, LoadManager.FadeType.ToBlack, 1f, false);
				break;
			case "equip": gun.Equip(); break;
			case "holster": gun.Holster(); break;
			case "fire": gun.Fire(int.Parse(a[1])); break;
			case "size": gun.SizePreset = int.Parse(a[1]); break;
			case "cyclesize": gun.CycleSize(int.Parse(a[1])); break;
			case "clear": PortalSystem.Instance.ClearAll(); break;
			case "look":
			{
				// look <yaw delta degrees> <absolute pitch degrees>
				var body = Locator.GetPlayerBody();
				body.SetRotation(Quaternion.AngleAxis(F(a, 1, 0), body.transform.up) * body.transform.rotation);
				Locator.GetPlayerCameraController().SetDegreesY(F(a, 2, 0));
				break;
			}
			case "push":
			{
				// push <right> <up> <forward> m/s relative to the camera, added to the current velocity
				var body = Locator.GetPlayerBody();
				var t = cam.transform;
				body.AddVelocityChange(t.right * F(a, 1, 0) + t.up * F(a, 2, 0) + t.forward * F(a, 3, 0));
				break;
			}
			case "move":
			{
				// move <right> <up> <forward> metres relative to the camera (instant)
				var body = Locator.GetPlayerBody();
				var t = cam.transform;
				body.WarpToPositionRotation(body.transform.position + t.right * F(a, 1, 0) + t.up * F(a, 2, 0) + t.forward * F(a, 3, 0), body.transform.rotation);
				break;
			}
			case "shot":
			{
				var path = Path.Combine(Path.Combine(PortalGunMod.Instance.ModFolder, "shots"), a[1] + ".png");
				ScreenCapture.CaptureScreenshot(path);
				Append("screenshot " + path);
				break;
			}
			case "dump": Dump(); break;
			case "dumptools": DumpTools(); break;
			case "ship":
			{
				// ship <right> <up> <forward> metres from the camera: park the ship there, at rest relative to the player
				var ship = Locator.GetShipBody();
				var t = cam.transform;
				ship.WarpToPositionRotation(t.position + t.right * F(a, 1, 0) + t.up * F(a, 2, 0) + t.forward * F(a, 3, 0), ship.transform.rotation);
				var ground = Locator.GetPlayerController().GetGroundBody();
				ship.SetVelocity(ground != null ? ground.GetPointVelocity(ship.GetPosition()) : Locator.GetPlayerBody().GetVelocity());
				ship.SetAngularVelocity(Vector3.zero);
				break;
			}
			case "shipabove":
			{
				// shipabove <0|1> <height>: ship's centre of mass straight above a portal, at rest relative to its surface
				var p = PortalSystem.Instance.Portals[int.Parse(a[1])];
				var ship = Locator.GetShipBody();
				var offset = ship.GetWorldCenterOfMass() - ship.GetPosition();
				var target = p.transform.position + p.transform.forward * F(a, 2, 30f);
				ship.WarpToPositionRotation(target - offset, ship.transform.rotation);
				ship.SetVelocity(p.ParentBody != null ? p.ParentBody.GetPointVelocity(target) : Vector3.zero);
				ship.SetAngularVelocity(Vector3.zero);
				break;
			}
			case "shippush":
			{
				var ship = Locator.GetShipBody();
				var t = cam.transform;
				ship.AddVelocityChange(t.right * F(a, 1, 0) + t.up * F(a, 2, 0) + t.forward * F(a, 3, 0));
				break;
			}
			case "probetool":
				// take out the scout launcher (the game only allows it with the suit; this skips that check)
				Locator.GetToolModeSwapper().EquipToolMode(ToolMode.Probe);
				break;
			case "probe":
				HarmonyLib.AccessTools.Method(typeof(ProbeLauncher), "LaunchProbe").Invoke(Locator.GetToolModeSwapper().GetProbeLauncher(), null);
				Append($"probe launched: {Locator.GetProbe().IsLaunched()}");
				break;
			default:
				Append("unknown command " + a[0]);
				break;
		}
	}

	private static IEnumerator Trace(float seconds)
	{
		var until = Time.time + seconds;
		while (Time.time < until)
		{
			var sb = new StringBuilder("trace");
			var cp = Locator.GetPlayerCamera().transform.position;
			var sys = PortalSystem.Instance;
			if (sys != null)
			{
				sb.Append($" tp={sys.Teleports}");
				foreach (var p in sys.Portals)
					if (p != null)
					{
						var pb = Locator.GetPlayerBody();
						var rv = pb.GetVelocity() - (p.ParentBody != null ? p.ParentBody.GetPointVelocity(pb.GetPosition()) : Vector3.zero);
						sb.Append($" {p.name}:{p.LocalPoint(cp)} v{p.transform.InverseTransformDirection(rv):F1}");
					}
			}
			sb.Append($" grounded={Locator.GetPlayerController()?.IsGrounded()}");
			var probe = Locator.GetProbe();
			if (sys != null && probe != null && probe.IsLaunched() && sys.Portals[0] != null)
				sb.Append($" probe@blue {sys.Portals[0].LocalPoint(probe.transform.position):F1} kin {probe.GetOWRigidbody().IsKinematic()} anch {probe.IsAnchored()}" +
					(sys.Portals[1] != null ? $" probe@orange {sys.Portals[1].LocalPoint(probe.transform.position):F1}" : ""));
			var ship = Locator.GetShipBody();
			if (sys != null && ship != null && sys.Portals[0] != null && Vector3.Distance(ship.GetPosition(), cp) < 150f)
				sb.Append($" ship@blue {sys.Portals[0].LocalPoint(ship.GetWorldCenterOfMass()):F1}" +
					(sys.Portals[1] != null ? $" ship@orange {sys.Portals[1].LocalPoint(ship.GetWorldCenterOfMass()):F1}" : ""));
			Append(sb.ToString());
			yield return new WaitForSeconds(0.05f);
		}
	}

	private static IEnumerator FinishLoad()
	{
		while (!LoadManager.IsAsyncLoadComplete())
			yield return null;
		yield return new WaitForSecondsRealtime(1f);
		LoadManager.EnableAsyncLoadTransition();
		Append("async load transition enabled");
	}

	private static void Dump()
	{
		var sb = new StringBuilder();
		var cam = Locator.GetPlayerCamera();
		var body = Locator.GetPlayerBody();
		sb.Append($"scene {LoadManager.GetCurrentScene()} input {OWInput.GetInputMode()} ");
		if (body != null)
			sb.Append($"player pos {body.GetPosition()} vel {body.GetVelocity().magnitude:F2} up {body.transform.up} cam fwd {cam.transform.forward} pitch {Locator.GetPlayerCameraController().GetDegreesY():F1} ");
		sb.Append($"suit {Locator.GetPlayerSuit()?.IsWearingSuit()} tool {Locator.GetToolModeSwapper()?.GetToolMode()} ");
		var gun = PortalGun.Instance;
		if (gun != null) sb.Append($"gun equipped {gun.Equipped} last '{gun.LastResult}' ");
		var sys = PortalSystem.Instance;
		if (sys != null)
		{
			sb.Append($"teleports {sys.Teleports} ");
			foreach (var p in sys.Portals)
				if (p != null)
					sb.Append($"[{p.name} open {p.IsOpen} parent {p.transform.parent?.name} body {p.ParentBody?.name} dist {Vector3.Distance(p.transform.position, cam.transform.position):F1} local-cam {p.LocalPoint(cam.transform.position)}] ");
		}
		Append(sb.ToString());
	}

	private static void DumpTools()
	{
		var cam = Locator.GetPlayerCamera();
		Append($"camera {cam.name} cullingMask {Convert.ToString(cam.cullingMask, 2)} path {cam.mainCamera.actualRenderingPath} hdr {cam.mainCamera.allowHDR} msaa {cam.mainCamera.allowMSAA} near {cam.nearClipPlane} far {cam.farClipPlane} fov {cam.fieldOfView}");
		for (var l = 0; l < 32; l++)
		{
			var n = LayerMask.LayerToName(l);
			if (!string.IsNullOrEmpty(n))
				Append($"layer {l} {n} visible {(cam.cullingMask & (1 << l)) != 0}");
		}
		var swapper = Locator.GetToolModeSwapper();
		foreach (var tool in new Component[] { swapper.GetSignalScope(), swapper.GetProbeLauncher(), swapper.GetTranslator() })
		{
			if (tool == null) continue;
			foreach (var r in tool.GetComponentsInChildren<Renderer>(true))
			{
				var m = r.sharedMaterial;
				Append($"tool {tool.name}/{r.name} layer {LayerMask.LayerToName(r.gameObject.layer)} shader {m?.shader?.name} queue {m?.renderQueue} keywords [{string.Join(",", m?.shaderKeywords ?? new string[0])}]");
			}
		}
	}
}
