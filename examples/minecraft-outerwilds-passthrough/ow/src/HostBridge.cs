using System;
using Newtonsoft.Json.Linq;
using OWML.Common;
using UnityEngine;

namespace BlockCraft;

/// <summary>
/// The host's runtime: every frame, tell the guest where Outer Wilds' camera is, and hand it the ground
/// under the player so it can collide with the same terrain.
///
/// Per docs/CONTRACT.md, Outer Wilds owns the camera, so the pose sent here is authoritative and the guest
/// renders from it. Because the guest is a plain-pose consumer, the host does the axis conversion: Unity is
/// Y-up with +Z forward and yaw increases counter-clockwise seen from above, Minecraft's yaw 0 faces +Z and
/// increases clockwise, so yaw is mirrored and Z is negated. Those signs are listed as unverified in the
/// contract until the first-slice alignment oracle passes -- `dump` in the dev bridge prints the raw and the
/// converted pose so they can be checked against a screenshot.
/// </summary>
public sealed class HostBridge : MonoBehaviour
{
	public static HostBridge Instance;

	public HostLink Link;
	public Compositor Compositor;

	/// <summary>How often the ground under the player is re-sent, in seconds. The set is small and changes rarely.</summary>
	private const float GroundInterval = 0.5f;
	/// <summary>Radius of the column scan around the player, in metres (= blocks).</summary>
	private const int GroundRadius = 12;

	private long _hostFrame;
	private float _nextGround;
	private bool _groundSent;
	private OWCamera _cam;
	/** When set, the bridge stops sending poses so tools/oracle.py can hold a fixed camera. */
	public bool Holding { get; private set; }

	public void SetHold(bool holding)
	{
		Holding = holding;
	}

	public static HostBridge Create(HostLink link, Compositor compositor)
	{
		var go = new GameObject("BlockCraftBridge");
		// Same reason as the compositor: this is created during a scene load, so it has to survive it or
		// the guest never receives a camera pose.
		UnityEngine.Object.DontDestroyOnLoad(go);
		var b = go.AddComponent<HostBridge>();
		b.Link = link;
		b.Compositor = compositor;
		Instance = b;
		return b;
	}

	private void Start()
	{
		// Subscribe in Start, not OnEnable. The compositor's identical hook works because it subscribes
		// here; a component added to an object that was pulled into DontDestroyOnLoad during a scene load
		// can have its OnEnable skipped, which left this bridge (and the dev bridge) inert while the
		// compositor kept drawing.
		Camera.onPreCull += OnPreCullTick;
	}

	private void Update()
	{
		Tick();
	}

	/// <summary>
	/// See <see cref="DevBridge"/>: a component created during a scene transition can have a dead
	/// <c>Update</c> while its static-event callbacks still fire. Driving from <c>Camera.onPreCull</c> too
	/// means the guest keeps receiving camera poses either way, which it needs to publish any frame at all.
	/// </summary>
	private void OnEnable()
	{
		Camera.onPreCull -= OnPreCullTick;
		Camera.onPreCull += OnPreCullTick;
	}

	private void OnDisable()
	{
		Camera.onPreCull -= OnPreCullTick;
	}

	private void OnDestroy()
	{
		Camera.onPreCull -= OnPreCullTick;
	}

	private void OnPreCullTick(Camera cam)
	{
		Tick();
	}

	private void Tick()
	{
		if (Link == null) return;

		// Drain whatever the guest sent: hello (mapping name), bye.
		Link.Drain(OnGuestMessage);

		// The oracle holds the camera itself; sending our own pose would overwrite it every frame.
		if (Holding) return;

		// Re-resolve every frame. `_cam ??=` cached a reference across scene loads, and a Unity object
		// that survives a scene change is non-null in C# while being destroyed in Unity: reading its
		// transform then throws, which killed the rest of Tick and silently stopped every pose.
		var cam = Locator.GetPlayerCamera();
		if (cam == null)
		{
			return;
		}

		_cam = cam;
		SendCamera();
		if (Time.unscaledTime >= _nextGround)
		{
			_nextGround = Time.unscaledTime + GroundInterval;
			SendGround();
		}
	}

	private void OnGuestMessage(JObject m)
	{
		var t = m["t"]?.ToString();
		switch (t)
		{
			case "hello":
			{
				var shm = m["shm"]?.ToString();
				if (!string.IsNullOrEmpty(shm) && Compositor != null && Compositor.ShmName != shm)
				{
					Compositor.ShmName = shm;
					Compositor.Reader?.Dispose();
					Compositor.Reader = null;
				}

				var pid = m["pid"]?.ToObject<int>() ?? 0;
				BlockCraftMod.Log($"guest hello: shm {shm}, pid {pid}");
				break;
			}
			case "bye":
				BlockCraftMod.Log("guest said goodbye: " + (m["reason"]?.ToString() ?? ""));
				break;
		}
	}

	/// <summary>Unity pose -> Minecraft coordinates, per docs/CONTRACT.md.</summary>
	private void SendCamera()
	{
		var t = _cam.transform;
		var pos = t.position;
		var e = t.eulerAngles; // Unity yaw is degrees, 0..360, counter-clockwise from +Z

		// Contract: MC = (OW.x, OW.y, -OW.z); MC.yaw = 180 - OW.yaw; MC.pitch = -OW.pitch.
		var x = pos.x;
		var y = pos.y;
		var z = -pos.z;
		var yaw = Mathf.Repeat(180f - e.y, 360f);
		var pitch = -Normalize(e.x);
		var roll = -Normalize(e.z);

		var message = new JObject
		{
			["t"] = "cam",
			["f"] = _hostFrame++,
			["p"] = new JArray(x, y, z),
			["r"] = new JArray(yaw, pitch, roll),
			["fov"] = Fov(),
			["fp"] = true,
			["pl"] = new JArray(x, y, z),
			["h"] = yaw
		};
		Link.Send(message);
	}

	/// <summary>Unity euler x/z come back 0..360; return -180..180 so the sign conversion is meaningful.</summary>
	private static float Normalize(float deg) => Mathf.DeltaAngle(0f, deg);

	private float Fov()
	{
		var cam = _cam.mainCamera;
		return cam != null ? cam.fieldOfView : 70f;
	}

	/// <summary>
	/// Send the solid columns near the player: {x, z, yBottom, yTop, ...} in Minecraft block coordinates.
	/// A vertical raycast per column gives the ground the guest should be able to stand on; the guest turns
	/// these into barriers so its player collides with the same terrain.
	/// </summary>
	private void SendGround()
	{
		var player = Locator.GetPlayerBody();
		if (player == null) return;
		var centre = player.GetPosition();
		var up = player.transform.up;

		// Gather columns in the host's own XZ, then convert to Minecraft's axes the same way as the pose.
		var columns = new System.Collections.Generic.List<int>();
		var origin = new Vector3Int(Mathf.FloorToInt(centre.x), 0, Mathf.FloorToInt(centre.z));
		for (var dx = -GroundRadius; dx <= GroundRadius; dx++)
		for (var dz = -GroundRadius; dz <= GroundRadius; dz++)
		{
			var wx = origin.x + dx;
			var wz = origin.z + dz;
			// column over a spot near the player, from above to below: first hit is the surface
			var probe = new Vector3(wx + 0.5f, centre.y + 4f, wz + 0.5f);
			if (!Physics.Raycast(probe, -up, out var hit, 40f, ~0, QueryTriggerInteraction.Ignore))
				continue;

			var surface = hit.point;
			var bottom = Mathf.FloorToInt(surface.y);
			// one block of ground under the surface, converted to Minecraft's axes
			columns.Add(Mathf.FloorToInt(surface.x));
			columns.Add(-Mathf.FloorToInt(surface.z));
			columns.Add(bottom - 1);
			columns.Add(bottom);
		}

		Link.Send(new JObject { ["t"] = "ground", ["c"] = new JArray(columns) });
		_groundSent = true;
	}

	public void ClearGround()
	{
		if (!_groundSent) return;
		Link.Send(new JObject { ["t"] = "clear" });
		_groundSent = false;
	}

	/// <summary>A one-line state dump for the dev bridge and the log.</summary>
	public string Pose()
	{
		if (_cam == null) return "no camera";
		var t = _cam.transform;
		var e = t.eulerAngles;
		return $"ow pos {t.position:F3} euler {e:F2} fov {Fov():F1} | " +
			$"mc pos ({t.position.x:F3},{t.position.y:F3},{-t.position.z:F3}) " +
			$"yaw {Mathf.Repeat(180f - e.y, 360f):F2} pitch {-Normalize(e.x):F2}";
	}
}
