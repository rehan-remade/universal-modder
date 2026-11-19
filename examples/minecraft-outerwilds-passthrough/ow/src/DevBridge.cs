using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace BlockCraft;

/// <summary>
/// Test oracle for agents and developers. Off unless `dev.enabled` exists in the mod folder.
/// Write lines to `dev_commands.txt`; they run in order and results go to `dev_log.txt`.
///
/// Written for this project from the outer-wilds-portal-gun example's DevBridge, trimmed to the commands
/// the passthrough needs to be driven without a human at the keyboard: place/move the guest's screen,
/// take screenshots, dump the pose on both the host and the guest side, and wait on world conditions.
/// </summary>
public class DevBridge : MonoBehaviour
{
	private static string s_logPath;
	private string _cmdPath;
	private readonly Queue<string> _queue = new();
	private bool _running;
	/** Byte offset of the next unread command line in dev_commands.txt. */
	private long _offset;
	/** Whether the one-off component-state report has been written. */
	private bool _reported;
	/** How many times Poll() ran; proves which drive path is alive. */
	private long _updateRuns;
	private static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

	private void Start()
	{
		var folder = BlockCraftMod.Instance.ModFolder;
		if (!File.Exists(Path.Combine(folder, "dev.enabled")))
		{
			enabled = false;
			return;
		}

		_cmdPath = Path.Combine(folder, "dev_commands.txt");
		s_logPath = Path.Combine(folder, "dev_log.txt");
		Directory.CreateDirectory(Path.Combine(folder, "shots"));

		// Start reading from the end of whatever is already there. An external writer appends command
		// lines; anything present at startup is stale (left over from a previous session) and replaying
		// it would fire commands nobody asked for. tools/slice1.sh truncates the file before writing for
		// the same reason.
		try
		{
			_offset = File.Exists(_cmdPath) ? new FileInfo(_cmdPath).Length : 0;
		}
		catch (IOException)
		{
			_offset = 0;
		}

		// Subscribe in Start, which is what demonstrably runs for a component created during a scene load
		// (the compositor subscribes here and has never gone deaf). OnEnable can be skipped for these.
		Camera.onPreCull -= OnPreCull;
		Camera.onPreCull += OnPreCull;
		Append("dev bridge on");
	}

	private void OnDestroy()
	{
		// Camera.onPreCull is static and is not cleared between scenes, so a subscription that outlives its
		// component would keep ticking a destroyed object. Unsubscribing here keeps the event honest.
		Camera.onPreCull -= OnPreCull;
	}

	public static void Append(string line)
	{
		if (s_logPath == null) return;
		try
		{
			File.AppendAllText(s_logPath, $"[{DateTime.Now:HH:mm:ss.fff} f{Time.frameCount}] {line}\n");
		}
		catch (IOException)
		{
		}
	}

	/// <summary>
	/// Read command lines appended since the last frame.
	///
	/// <p>This used to read the whole file and then delete it, which loses commands: a line appended
	/// between the read and the delete disappears unread, and the delete races the writer. Tracking a
	/// byte offset instead means the writer never has to cooperate beyond appending, and no line can be
	/// skipped or run twice. The file is deliberately <b>not</b> deleted, so the last commands stay
	/// visible for debugging; `slice1.sh` truncates it when it wants a clean slate.
	/// </summary>
	private void Update()
	{
		Poll();
	}

	/// <summary>
	/// Diagnostics for the "Start() runs but Update() never does" problem this mod hit on its first host run.
	///
	/// <p>Unity only calls <c>Update</c> on components whose GameObject is active and enabled. The compositor
	/// was unaffected because it drives itself from the static <c>Camera.onPreCull</c> event instead, which
	/// fires regardless. So a component created during a scene transition can look alive (its callback still
	/// runs) while its <c>Update</c> is silently dead. Everything this class needs per-frame therefore also
	/// runs from <c>onPreCull</c>, and the state is logged once so the cause is visible rather than guessed.
	/// </summary>
	private void OnEnable()
	{
		Camera.onPreCull -= OnPreCull;
		Camera.onPreCull += OnPreCull;
	}

	private void OnDisable()
	{
		Camera.onPreCull -= OnPreCull;
	}

	private void OnPreCull(Camera cam)
	{
		Poll();
		ReportStateOnce();
	}

	/// <summary>
	/// Log where this component actually lives, once. If <c>Update</c> is ever dead again, this says whether
	/// the GameObject was deactivated, the component was disabled, or the object was destroyed outright.
	/// </summary>
	private void ReportStateOnce()
	{
		if (_reported) return;
		_reported = true;
		Append($"state: activeSelf={gameObject.activeSelf} activeInHierarchy={gameObject.activeInHierarchy} " +
			$"enabled={enabled} scene='{gameObject.scene.name}' updateRuns={_updateRuns} frame={Time.frameCount}");
	}

	private void Poll()
	{
		_updateRuns++;
		try
		{
			if (_cmdPath != null && File.Exists(_cmdPath))
			{
				using var stream = new FileStream(_cmdPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
				if (stream.Length > _offset)
				{
					stream.Seek(_offset, SeekOrigin.Begin);
					using var reader = new StreamReader(stream);
					string l;
					while ((l = reader.ReadLine()) != null)
						if (!string.IsNullOrWhiteSpace(l) && !l.TrimStart().StartsWith("#"))
							_queue.Enqueue(l.Trim());
					_offset = stream.Length;
				}
			}
		}
		catch (IOException)
		{
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
			case "solarsystem":
				return LoadManager.GetCurrentScene() == OWScene.SolarSystem
					&& BlockCraftMod.Instance != null && !LoadManager.IsBusy();
			case "title":
				return LoadManager.GetCurrentScene() == OWScene.TitleScreen && !LoadManager.IsBusy();
			case "control":
				return OWInput.IsInputMode(InputMode.Character);
			case "guest":
				return HostBridge.Instance?.Link?.Connected == true;
			case "frames":
				// the host has actually read a guest frame, not just connected
				return Compositor.Instance != null && Compositor.Instance.FrameReads > 0;
			default:
				return false;
		}
	}

	private void Exec(string[] a)
	{
		var bridge = HostBridge.Instance;
		var comp = Compositor.Instance;
		var cam = Locator.GetPlayerCamera();
		switch (a[0])
		{
			case "shot":
			{
				var path = Path.Combine(Path.Combine(BlockCraftMod.Instance.ModFolder, "shots"), a[1] + ".png");
				ScreenCapture.CaptureScreenshot(path);
				Append("screenshot " + path);
				break;
			}
			case "place":
				// place [distance]: put the guest's screen in front of the camera
				comp?.PlaceInFront(F(a, 1, 6f));
				Append("place -> " + (comp != null ? comp.ScreenPosition.ToString("F2") : "no compositor"));
				break;
			case "size":
				comp?.SetSize(F(a, 1, 3.2f), F(a, 2, 1.8f));
				Append($"size {comp?.ScreenWidth:F2}x{comp?.ScreenHeight:F2}");
				break;
			case "at":
				// at x y z [nx ny nz]: place the screen at an explicit world spot and normal
				if (comp != null && a.Length >= 4)
				{
					comp.ScreenPosition = new Vector3(F(a, 1, 0), F(a, 2, 0), F(a, 3, 0));
					comp.ScreenNormal = a.Length >= 7
						? new Vector3(F(a, 4, 0), F(a, 5, 0), F(a, 6, 1)).normalized
						: Vector3.up;
				}

				Append("at -> " + (comp != null ? comp.ScreenPosition.ToString("F2") : "no compositor"));
				break;
			case "pose":
			case "dump":
				Append("host: " + (bridge?.Pose() ?? "no bridge"));
				Append("guest: " + (comp?.Status() ?? "no compositor"));
				if (comp != null)
					Append($"screen pos {comp.ScreenPosition:F2} normal {comp.ScreenNormal:F2} " +
						$"size {comp.ScreenWidth:F2}x{comp.ScreenHeight:F2} frames {comp.FrameReads} misses {comp.FrameMisses}");
				if (bridge?.Link != null)
					Append($"link: connected {bridge.Link.Connected} sent {bridge.Link.Sent} recv {bridge.Link.Received} " +
						$"errors {bridge.Link.Errors} shm {bridge.Link.GuestShm} pid {bridge.Link.GuestPid}");
				if (comp?.Reader != null)
					Append($"reader: reads {comp.Reader.Reads} torn {comp.Reader.Torn} missed {comp.Reader.Missed} " +
						$"publish {comp.Reader.PublishCounter} slot {comp.Reader.LatestSlot} " +
						$"max {comp.Reader.MaxWidth}x{comp.Reader.MaxHeight}");
				break;
			case "clearground":
				bridge?.ClearGround();
				Append("ground cleared");
				break;
			case "cmd":
				// cmd <text...>: a Minecraft command, passed through to the guest
				bridge?.Link?.Send(new Newtonsoft.Json.Linq.JObject
				{
					["t"] = "cmd",
					["c"] = string.Join(" ", a, 1, a.Length - 1)
				});
				Append("cmd sent");
				break;
			case "fov":
				Append($"camera fov {cam?.mainCamera?.fieldOfView:F1}");
				break;
			case "oracle":
				// oracle [on|off]: stop the host bridge sending poses, so an outside client (tools/oracle.py)
				// can hold a fixed camera and compare the rendered frame against known geometry. Without
				// this the host's own per-frame pose overwrites the oracle's and the test measures the
				// player's camera instead of the one it asked for.
				bridge?.SetHold(a.Length > 1 && a[1] == "on");
				Append($"oracle hold {(bridge != null && bridge.Holding ? "on" : "off")}");
				break;
			case "state":
				// state: the objective facts that decide whether poses can be sent at all. A null player
				// camera silently stops the bridge, which looks exactly like a frozen guest picture.
				var body = Locator.GetPlayerBody();
				var scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
				Append($"state: paused {OWTime.IsPaused()} timeScale {Time.timeScale:F2} " +
					$"scene '{scene.name}' loaded {scene.isLoaded} " +
					$"body {(body == null ? "null" : "ok")} camera {(cam == null ? "null" : "ok")} " +
					$"holding {(bridge != null && bridge.Holding)}");
				break;
			default:
				Append("unknown command " + a[0]);
				break;
		}
	}
}
