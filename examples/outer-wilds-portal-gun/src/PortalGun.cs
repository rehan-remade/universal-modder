using System.Collections;
using UnityEngine;
using UnityEngine.InputSystem;

namespace OWPortalGun;

/// <summary>
/// The held tool. Lives outside the game's ToolModeSwapper (which only knows its four tools): the equip key
/// puts away whatever the swapper holds, and taking out a game tool puts this one away.
/// </summary>
public class PortalGun : MonoBehaviour
{
	public static PortalGun Instance;

	public const float FireInterval = 0.5f;   // Portal 2: 0.5 s between shots
	public const float MaxRange = 1500f;
	public const float BoltSpeed = 900f;
	public static readonly Vector2 PortalSize = new(1.6f, 2.6f);
	public static readonly float[] SizePresets = { 1f, 2f, 5f };

	public bool Equipped { get; private set; }
	public int SizePreset;
	public Renderer ViewmodelRenderer => _vm != null ? _vmRenderer : null;
	public string LastResult = "";

	private GunAssets _assets;
	private PortalSystem _system;
	private Viewmodel _vm;
	private Renderer _vmRenderer;
	private OWCamera _cam;
	private ToolModeSwapper _swapper;
	private AudioSource _audio;
	private float _nextFire;
	private bool _holstering;
	private bool _waitSwapper;
	private Key _equipKey = Key.Digit5;
	private PortalHud _hud;

	public static PortalGun Create(GunAssets assets, PortalSystem system)
	{
		var go = new GameObject("PortalGun");
		go.transform.SetParent(system.transform, false);
		var g = go.AddComponent<PortalGun>();
		g._assets = assets;
		g._system = system;
		Instance = g;
		return g;
	}

	private void Start()
	{
		_cam = Locator.GetPlayerCamera();
		_swapper = Locator.GetToolModeSwapper();
		Materials.InitFromGame(_swapper);
		_vm = Viewmodel.Create(_assets, _cam.transform, LayerMask.NameToLayer("VisibleToPlayer"));
		_vmRenderer = _vm.GetComponentInChildren<SkinnedMeshRenderer>();
		_vm.gameObject.SetActive(false);
		_hud = gameObject.AddComponent<PortalHud>();
		_hud.Init(_assets);
		_audio = gameObject.AddComponent<AudioSource>();
		_audio.spatialBlend = 0f;
		_audio.playOnAwake = false;
		_equipKey = ParseKey(PortalGunMod.Instance.EquipKey);
		PortalGunMod.Log($"portal gun ready: camera '{_cam.name}' layer {LayerMask.LayerToName(_cam.gameObject.layer)} near {_cam.nearClipPlane:F3} fov {_cam.fieldOfView:F1}, equip key {_equipKey}");
	}

	private void OnDestroy()
	{
		if (Instance == this) Instance = null;
	}

	private static Key ParseKey(string s)
	{
		if (string.IsNullOrEmpty(s)) return Key.Digit5;
		// Key.Digit1..Digit9 are consecutive and Digit0 comes after Digit9.
		if (s.Length == 1 && char.IsDigit(s[0])) return s[0] == '0' ? Key.Digit0 : Key.Digit1 + (s[0] - '1');
		return System.Enum.TryParse<Key>(s, true, out var k) ? k : Key.Digit5;
	}

	// --- equip --------------------------------------------------------------------------------------

	/// <summary>States that take the player's hands: the gun goes away, like the game's own tools.</summary>
	private static bool HandsBusy() =>
		PlayerState.InDreamWorld() || PlayerState.IsAttached() || PlayerState.InConversation() || PlayerState.IsDead();

	/// <summary>Can the player act right now (not in a menu, the map, or a cutscene)?</summary>
	private static bool CanUse() => OWInput.IsInputMode(InputMode.Character) && !HandsBusy();

	private void Update()
	{
		var kb = Keyboard.current;
		if (kb != null && kb[_equipKey].wasPressedThisFrame && OWInput.IsInputMode(InputMode.Character))
			Toggle();

		if (Equipped)
		{
			// Taking out a game tool, sitting at a console or entering the dream world puts the gun away.
			var mode = _swapper.GetToolMode();
			if (_waitSwapper && mode == ToolMode.None)
				_waitSwapper = false;
			if ((mode != ToolMode.None && !_waitSwapper) || HandsBusy())
				Holster();
			else if (OWInput.IsInputMode(InputMode.Character))
			{
				ReadFireInput();
				if (Mouse.current != null && Mouse.current.scroll.ReadValue().y != 0f)
					CycleSize(Mouse.current.scroll.ReadValue().y > 0 ? 1 : -1);
			}
		}
		if (_holstering && _vm.Finished)
		{
			_holstering = false;
			_vm.gameObject.SetActive(false);
		}
	}

	public void Toggle()
	{
		if (Equipped) Holster();
		else Equip();
	}

	public void Equip()
	{
		if (Equipped || !CanUse())
			return;
		var item = _swapper.GetItemCarryTool();
		if (item != null && item.GetHeldItem() != null)
		{
			Notify(PortalHud.T("Drop what you're carrying to use the portal gun", "Soltá lo que llevás para usar el arma de portales"));
			return;
		}
		// The swapper keeps reporting the old tool until it has finished stowing it.
		_waitSwapper = _swapper.GetToolMode() != ToolMode.None;
		if (_waitSwapper)
			_swapper.UnequipTool();
		Equipped = true;
		_holstering = false;
		_vm.gameObject.SetActive(true);
		_vm.Play("draw");
		Play("wpn_portalgun_activation_01", 0.6f);
		Locator.GetPlayerAudioController()?.PlayEquipTool();
	}

	public void Holster()
	{
		if (!Equipped)
			return;
		Equipped = false;
		_holstering = true;
		_vm.Play("holster", null);
		Locator.GetPlayerAudioController()?.PlayUnequipTool();
	}

	public void CycleSize(int dir)
	{
		SizePreset = Mathf.Clamp(SizePreset + dir, 0, SizePresets.Length - 1);
		var name = PortalHud.T(new[] { "normal", "large", "ship" }[SizePreset], new[] { "normal", "grande", "nave" }[SizePreset]);
		Notify(PortalHud.T("Portal size", "Tamaño de portal") + $": {name} ({PortalSize.x * SizePresets[SizePreset]:F1} x {PortalSize.y * SizePresets[SizePreset]:F1} m)");
	}

	/// <summary>
	/// Called from the ToolModeSwapper.Update prefix: while the gun is out, the game must not see the tool buttons
	/// (right mouse would take out the scout launcher, R is the tool's secondary action).
	/// </summary>
	public void ConsumeGameToolInput()
	{
		if (!Equipped)
			return;
		InputLibrary.toolActionPrimary.ConsumeInput();
		InputLibrary.toolActionSecondary.ConsumeInput();
	}

	/// <summary>
	/// Portal controls: left mouse = blue, right mouse = orange (gamepad: RB blue, LB orange). Read from the devices
	/// directly because the game binds right mouse to "tool primary" and left mouse to lock-on.
	/// </summary>
	private void ReadFireInput()
	{
		var mouse = Mouse.current;
		var pad = Gamepad.current;
		var blue = (mouse != null && mouse.leftButton.wasPressedThisFrame) || (pad != null && pad.rightShoulder.wasPressedThisFrame);
		var orange = (mouse != null && mouse.rightButton.wasPressedThisFrame) || (pad != null && pad.leftShoulder.wasPressedThisFrame);
		if (blue) Fire(0);
		else if (orange) Fire(1);
	}

	// --- firing ---------------------------------------------------------------------------------------

	public void Fire(int color)
	{
		if (!Equipped || Time.time < _nextFire)
			return;
		_nextFire = Time.time + FireInterval;
		_vm.Play("fire1");
		_vm.SetSkin(color + 1);
		Play(color == 0 ? $"wpn_portal_gun_fire_blue_0{Random.Range(1, 4)}" : $"wpn_portal_gun_fire_red_0{Random.Range(1, 4)}", 0.8f);

		var origin = _cam.transform.position;
		var dir = _cam.transform.forward;
		var muzzle = _vm.Attachment("muzzle").position;
		StartCoroutine(Shoot(color, origin, dir, muzzle));
	}

	private IEnumerator Shoot(int color, Vector3 origin, Vector3 dir, Vector3 muzzle)
	{
		var size = PortalSize * SizePresets[SizePreset];
		var travelled = 0f;
		var boltFrom = muzzle;
		for (var bounce = 0; bounce < 4; bounce++)
		{
			if (!Physics.Raycast(origin, dir, out var hit, MaxRange - travelled, OWLayerMask.physicalMask, QueryTriggerInteraction.Ignore))
			{
				yield return Bolt(color, boltFrom, origin + dir * 200f);
				LastResult = "miss";
				yield break;
			}
			// Shots that go into an open portal come out of the other one.
			var through = ThroughPortal(origin, dir, hit.distance, out var entry, out var hitDist);
			if (through != null)
			{
				var enter = origin + dir * hitDist;
				yield return Bolt(color, boltFrom, enter);
				travelled += hitDist;
				origin = through.MapPoint(enter) + through.Linked.transform.forward * 0.05f;
				dir = through.MapDirection(dir);
				boltFrom = origin;
				continue;
			}
			var localHit = hit.collider.transform.InverseTransformPoint(hit.point);
			var localNormal = hit.collider.transform.InverseTransformDirection(hit.normal);
			yield return Bolt(color, boltFrom, hit.point);
			if (hit.collider == null)
				yield break;
			// The surface may have moved while the bolt flew.
			var point = hit.collider.transform.TransformPoint(localHit);
			var normal = hit.collider.transform.TransformDirection(localNormal).normalized;
			TryPlace(color, size, point, normal, hit.collider, dir);
			yield break;
		}
	}

	private Portal ThroughPortal(Vector3 origin, Vector3 dir, float maxDist, out Portal entry, out float dist)
	{
		entry = null;
		dist = maxDist;
		foreach (var p in _system.Portals)
		{
			if (p == null || p.Linked == null || !p.IsOpen || !p.Linked.IsOpen)
				continue;
			var plane = new Plane(p.transform.forward, p.transform.position);
			if (Vector3.Dot(dir, p.transform.forward) >= 0f || !plane.Raycast(new Ray(origin, dir), out var d) || d > dist + 0.1f)
				continue;
			if (p.InsideEllipse(p.LocalPoint(origin + dir * d)))
			{
				entry = p;
				dist = d;
			}
		}
		return entry;
	}

	private IEnumerator Bolt(int color, Vector3 from, Vector3 to)
	{
		var go = new GameObject("PortalBolt");
		var lr = go.AddComponent<LineRenderer>();
		lr.material = Materials.Unlit(Texture2D.whiteTexture, color == 0 ? new Color(0.3f, 0.6f, 1f, 0.9f) : new Color(1f, 0.6f, 0.2f, 0.9f), true, 3002);
		lr.widthMultiplier = 0.06f;
		lr.positionCount = 2;
		lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
		var len = (to - from).magnitude;
		var t = 0f;
		var dur = Mathf.Max(0.04f, len / BoltSpeed);
		while (t < dur)
		{
			t += Time.deltaTime;
			var a = Mathf.Clamp01((t - 0.03f) / dur);
			var b = Mathf.Clamp01(t / dur);
			lr.SetPosition(0, Vector3.Lerp(from, to, a));
			lr.SetPosition(1, Vector3.Lerp(from, to, b));
			yield return null;
		}
		Destroy(go);
	}

	/// <summary>Places a portal if its ellipse fits on the surface, nudging it like Portal 2 does.</summary>
	private void TryPlace(int color, Vector2 size, Vector3 point, Vector3 normal, Collider wall, Vector3 shotDir)
	{
		var other = _system.Portals[1 - color];
		var up0 = PortalUp(normal, shotDir);
		var right0 = Vector3.Cross(up0, normal);
		foreach (var offset in Nudges(size))
		{
			var c = point + right0 * offset.x + up0 * offset.y;
			if (!Fits(c, normal, size, shotDir, out var surface, out var n, out var walls))
				continue;
			if (other != null && other.IsOpen && Vector3.Distance(other.transform.position, surface) < Mathf.Max(size.x, other.Size.x) * 0.9f
				&& Vector3.Dot(other.transform.forward, n) > 0.9f)
				continue;
			var up = PortalUp(n, shotDir);
			var p = _system.Place(color, size, surface, Quaternion.LookRotation(n, up), wall, walls);
			p.Audio.volume = PortalGunMod.Instance.Volume;
			PlayAt(p.Audio, color == 0 ? "portal_open_blue_01" : $"portal_open_red_0{Random.Range(1, 3)}");
			var upDot = Vector3.Dot(n, Locator.GetPlayerTransform().up);
			LastResult = $"placed {(color == 0 ? "blue" : "orange")} on {wall.name} ({wall.GetAttachedOWRigidbody()?.name}) +{walls.Length - 1} colliders, offset {offset} " +
				$"dist {Vector3.Distance(_cam.transform.position, surface):F1} m, normal.up {upDot:F2}";
			PortalGunMod.Log(LastResult);
			return;
		}
		LastResult = $"invalid surface {wall.name} dist {Vector3.Distance(_cam.transform.position, point):F1} m ({_fitReason})";
		PortalGunMod.Log(LastResult);
		var src = new GameObject("PortalInvalid").AddComponent<AudioSource>();
		src.transform.position = point;
		src.spatialBlend = 1f;
		src.minDistance = 2f;
		src.maxDistance = 60f;
		src.volume = PortalGunMod.Instance.Volume;
		PlayAt(src, $"portal_invalid_surface_0{Random.Range(1, 5)}");
		Destroy(src.gameObject, 3f);
	}

	private static System.Collections.Generic.IEnumerable<Vector2> Nudges(Vector2 size)
	{
		yield return Vector2.zero;
		var sx = size.x * 0.25f;
		var sy = size.y * 0.25f;
		for (var r = 1; r <= 3; r++)
		{
			yield return new Vector2(0, sy * r);
			yield return new Vector2(0, -sy * r);
			yield return new Vector2(sx * r, 0);
			yield return new Vector2(-sx * r, 0);
		}
	}

	private Vector3 PortalUp(Vector3 normal, Vector3 shotDir)
	{
		var grav = Locator.GetPlayerForceDetector() != null ? Locator.GetPlayerForceDetector().GetForceAcceleration() : Vector3.zero;
		var worldUp = grav.sqrMagnitude > 0.01f ? -grav.normalized : Locator.GetPlayerTransform().up;
		Vector3 up;
		if (Mathf.Abs(Vector3.Dot(normal, worldUp)) > 0.7f)
			up = Vector3.ProjectOnPlane(shotDir, normal);   // floor/ceiling: top of the portal away from the shooter
		else
			up = Vector3.ProjectOnPlane(worldUp, normal);
		if (up.sqrMagnitude < 1e-4f)
			up = Vector3.ProjectOnPlane(_cam.transform.up, normal);
		return up.normalized;
	}

	/// <summary>
	/// Fits the portal to the surface the way natural terrain needs: samples the outline and the inside, fits an
	/// average plane, and accepts up to about a metre of unevenness. The portal sits on the most protruding
	/// sample so rock never pokes through its face. Fails over edges, holes and overhangs.
	/// </summary>
	private string _fitReason = "";

	private bool Fits(Vector3 c, Vector3 n0, Vector2 size, Vector3 shotDir, out Vector3 surface, out Vector3 normal, out Collider[] walls)
	{
		surface = c;
		normal = n0;
		walls = null;
		var lift = Mathf.Max(1.2f, size.y * 0.3f);
		var mask = OWLayerMask.physicalMask;
		if (!Physics.Raycast(c + n0 * lift, -n0, out var centre, lift * 2.5f, mask, QueryTriggerInteraction.Ignore))
		{
			_fitReason = "no centre hit";
			return false;
		}
		var up = PortalUp(n0, shotDir);
		var right = Vector3.Cross(up, n0);
		var pts = new System.Collections.Generic.List<Vector3> { centre.point };
		var nsum = centre.normal;
		var cols = new System.Collections.Generic.HashSet<Collider> { centre.collider };
		int misses = 0, blocked = 0, nohit = 0, steep = 0;
		const int ring = 12;
		for (var i = 0; i < ring + 4; i++)
		{
			var outer = i < ring;
			var a = outer ? i * Mathf.PI * 2f / ring : (i - ring) * Mathf.PI * 0.5f + Mathf.PI * 0.25f;
			var k = outer ? 0.5f : 0.25f;
			var o = right * (Mathf.Cos(a) * size.x * k) + up * (Mathf.Sin(a) * size.y * k);
			var start = centre.point + o + n0 * lift;
			if (Physics.CheckSphere(start, 0.05f, mask, QueryTriggerInteraction.Ignore))
			{
				misses++;
				blocked++;
				continue;
			}
			// A start point inside a hill sees nothing (rays don't hit back faces); retry from higher up.
			if (!Physics.Raycast(start, -n0, out var h, lift * 2f, mask, QueryTriggerInteraction.Ignore)
				&& !Physics.Raycast(start + n0 * lift * 2f, -n0, out h, lift * 4f, mask, QueryTriggerInteraction.Ignore))
			{
				misses++;
				nohit++;
				continue;
			}
			if (Vector3.Dot(h.normal, n0) < 0.2f)
			{
				misses++;
				steep++;
				continue;
			}
			pts.Add(h.point);
			nsum += h.normal;
			cols.Add(h.collider);
		}
		var big = size.y > 4f; // ship-sized portals on natural ground need more slack
		if (misses > (big ? 4 : 2))
		{
			_fitReason = $"{misses} samples off the surface: {blocked} blocked, {nohit} no hit, {steep} steep";
			return false;
		}
		var n = (nsum.normalized + n0).normalized;
		float dmin = float.MaxValue, dmax = float.MinValue;
		foreach (var pt in pts)
		{
			var d = Vector3.Dot(pt - centre.point, n);
			dmin = Mathf.Min(dmin, d);
			dmax = Mathf.Max(dmax, d);
		}
		var maxSpread = 0.3f + size.y * (big ? 0.35f : 0.25f);
		if (dmax - dmin > maxSpread)
		{
			_fitReason = $"uneven {dmax - dmin:F1} m > {maxSpread:F1}";
			return false;
		}
		surface = centre.point + n * Mathf.Max(0f, dmax);
		normal = n;
		walls = new Collider[cols.Count];
		cols.CopyTo(walls);
		return true;
	}

	// --- feedback ------------------------------------------------------------------------------------

	public void OnTeleported(OWRigidbody body, Portal from, Portal to)
	{
		if (body.CompareTag("Player") || (body.CompareTag("Ship") && PlayerState.IsInsideShip()))
			Play($"portal_enter_0{Random.Range(1, 4)}", 0.5f);
		else
			PlayAt(to.Audio, $"portal_exit_0{Random.Range(1, 3)}");
	}

	private void Play(string sound, float volume)
	{
		if (_assets.Sounds.TryGetValue(sound, out var clip))
			_audio.PlayOneShot(clip, volume * PortalGunMod.Instance.Volume);
	}

	private void PlayAt(AudioSource src, string sound)
	{
		if (src != null && _assets.Sounds.TryGetValue(sound, out var clip))
			src.PlayOneShot(clip);
	}

	public static void Notify(string text)
	{
		if (Instance != null && Instance._hud != null)
			Instance._hud.Show(text);
	}
}
