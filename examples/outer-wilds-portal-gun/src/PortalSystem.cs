using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace OWPortalGun;

/// <summary>
/// Owns the two portals of the current loop: draws each portal's view, moves bodies through them and
/// handles collisions in the hole. Lives in the SolarSystem scene, so a loop reset wipes the portals.
/// </summary>
public class PortalSystem : MonoBehaviour
{
	public static PortalSystem Instance;

	public readonly Portal[] Portals = new Portal[2];
	public int Teleports;

	private OWCamera _playerCam;
	private Camera _mainCam;
	private GunAssets _assets;
	private readonly Dictionary<(Portal, OWRigidbody), Vector3> _prevLocal = new();
	private readonly Dictionary<(Portal, OWRigidbody), Collider[]> _ignoring = new();
	private readonly Dictionary<OWRigidbody, float> _cooldown = new();
	private readonly HashSet<OWRigidbody> _seen = new();
	private readonly Collider[] _overlap = new Collider[64];
	private MeshRenderer[] _composites = new MeshRenderer[2];
	private CommandBuffer _skybox;

	public static PortalSystem Create(GunAssets assets)
	{
		var go = new GameObject("PortalGunSystem");
		var s = go.AddComponent<PortalSystem>();
		s._assets = assets;
		Instance = s;
		return s;
	}

	private void Start()
	{
		_playerCam = Locator.GetPlayerCamera();
		_mainCam = _playerCam.mainCamera;
		Camera.onPreCull += OnAnyPreCull;
	}

	private void OnDestroy()
	{
		Camera.onPreCull -= OnAnyPreCull;
		foreach (var kv in _ignoring)
			if (_walls.TryGetValue(kv.Key, out var w))
				SetIgnore(w, kv.Value, false);
		for (var i = 0; i < 2; i++)
		{
			if (Portals[i] != null && Portals[i].Texture != null) Portals[i].Texture.Release();
			if (_composites[i] != null) Destroy(_composites[i].gameObject);
		}
		if (Instance == this) Instance = null;
	}

	// --- placing ------------------------------------------------------------------------------------

	public Portal Place(int color, Vector2 size, Vector3 pos, Quaternion rot, Collider wall, Collider[] walls)
	{
		var old = Portals[color];
		if (old != null)
		{
			ClearTracking(old);
			old.Close();
		}
		var p = Portal.Create(_assets, color, size, pos, rot, wall);
		p.Walls = walls ?? new[] { wall };
		Portals[color] = p;
		var other = Portals[1 - color];
		if (other != null)
		{
			p.Linked = other;
			other.Linked = p;
		}
		SetupView(p);
		return p;
	}

	public void ClearAll()
	{
		for (var i = 0; i < 2; i++)
			if (Portals[i] != null)
			{
				ClearTracking(Portals[i]);
				Portals[i].Close();
				Portals[i] = null;
			}
	}

	private void ClearTracking(Portal p)
	{
		var keys = new List<(Portal, OWRigidbody)>(_ignoring.Keys);
		foreach (var k in keys)
			if (k.Item1 == p)
			{
				if (_walls.TryGetValue(k, out var w))
					SetIgnore(w, _ignoring[k], false);
				_ignoring.Remove(k);
				_walls.Remove(k);
			}
		var pk = new List<(Portal, OWRigidbody)>(_prevLocal.Keys);
		foreach (var k in pk)
			if (k.Item1 == p)
				_prevLocal.Remove(k);
	}

	// --- rendering ------------------------------------------------------------------------------------

	private void SetupView(Portal p)
	{
		var camGo = new GameObject("view");
		camGo.transform.SetParent(transform, false);
		p.ViewCamera = camGo.AddComponent<Camera>();
		p.ViewCamera.enabled = false;
		EnsureTexture(p);

		// Full-screen quad on the player camera that shows the view where the stencil says "portal".
		var i = p.Color;
		if (_composites[i] == null)
		{
			var q = new GameObject(i == 0 ? "PortalCompositeBlue" : "PortalCompositeOrange");
			q.transform.SetParent(_mainCam.transform, false);
			q.AddComponent<MeshFilter>().sharedMesh = ScreenQuad();
			_composites[i] = q.AddComponent<MeshRenderer>();
			_composites[i].shadowCastingMode = ShadowCastingMode.Off;
			_composites[i].receiveShadows = false;
		}
		p.CompositeMat = Materials.StencilComposite(p.Texture, p.StencilRef, 2991);
		_composites[i].sharedMaterial = p.CompositeMat;
	}

	private void EnsureTexture(Portal p)
	{
		var w = Mathf.Max(64, _mainCam.pixelWidth);
		var h = Mathf.Max(64, _mainCam.pixelHeight);
		if (p.Texture != null && p.Texture.width == w && p.Texture.height == h)
			return;
		if (p.Texture != null) p.Texture.Release();
		var fmt = SystemInfo.SupportsRenderTextureFormat(RenderTextureFormat.RGB111110Float)
			? RenderTextureFormat.RGB111110Float : RenderTextureFormat.ARGBHalf;
		p.Texture = new RenderTexture(w, h, 24, fmt) { name = p.name + "_view" };
		p.Texture.Create();
		if (p.CompositeMat != null) p.CompositeMat.mainTexture = p.Texture;
	}

	private static Mesh ScreenQuad()
	{
		var m = new Mesh();
		m.vertices = new[] { new Vector3(-1, -1, 0), new Vector3(1, -1, 0), new Vector3(1, 1, 0), new Vector3(-1, 1, 0) };
		m.uv = new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(1, 1), new Vector2(0, 1) };
		m.triangles = new[] { 0, 2, 1, 0, 3, 2, 0, 1, 2, 0, 2, 3 };
		m.bounds = new Bounds(Vector3.zero, Vector3.one * 1000f);
		return m;
	}

	private bool _rendering;

	private void OnAnyPreCull(Camera cam)
	{
		if (_rendering || cam != _mainCam || _mainCam == null)
			return;
		_rendering = true;
		try
		{
			for (var i = 0; i < 2; i++)
				RenderPortal(Portals[i], i);
		}
		finally
		{
			_rendering = false;
		}
	}

	private void RenderPortal(Portal p, int i)
	{
		var comp = _composites[i];
		var active = p != null && p.Linked != null && p.IsOpen && p.Linked.IsOpen && IsVisible(p);
		if (p != null) p.StencilRenderer.enabled = active;
		if (comp != null) comp.enabled = active;
		if (!active)
			return;

		EnsureTexture(p);
		// Keep the composite quad just past the near plane and covering the whole view.
		var d = _mainCam.nearClipPlane * 1.05f;
		var hh = d * Mathf.Tan(_mainCam.fieldOfView * 0.5f * Mathf.Deg2Rad);
		comp.transform.localPosition = new Vector3(0, 0, d);
		comp.transform.localRotation = Quaternion.identity;
		comp.transform.localScale = new Vector3(hh * _mainCam.aspect * 1.02f, hh * 1.02f, 1f);

		var vc = p.ViewCamera;
		vc.CopyFrom(_mainCam);
		vc.enabled = false;
		vc.targetTexture = p.Texture;
		vc.rect = new Rect(0, 0, 1, 1);
		vc.transform.SetPositionAndRotation(p.MapPoint(_mainCam.transform.position), p.MapRotation(_mainCam.transform.rotation));
		vc.projectionMatrix = _mainCam.projectionMatrix;
		var exit = p.Linked.transform;
		var plane = CameraSpacePlane(vc, exit.position, exit.forward);
		if (Vector3.Dot(vc.transform.position - exit.position, exit.forward) < -0.05f)
			vc.projectionMatrix = vc.CalculateObliqueMatrix(plane);
		// Only render the part of the screen the portal covers (a distant portal costs a few pixels, not a frame).
		Scissor(vc, ScreenRect(p));
		AddSkybox(vc);

		// Hide what must not appear in the other side's picture: our own overlays and the held gun.
		var hidden = HideForView();
		try
		{
			vc.Render();
		}
		finally
		{
			foreach (var r in hidden) r.enabled = true;
		}
	}

	private readonly List<Renderer> _hidden = new();

	private List<Renderer> HideForView()
	{
		_hidden.Clear();
		void Hide(Renderer r)
		{
			if (r != null && r.enabled)
			{
				r.enabled = false;
				_hidden.Add(r);
			}
		}
		for (var i = 0; i < 2; i++)
		{
			Hide(_composites[i]);
			if (Portals[i] != null) Hide(Portals[i].StencilRenderer);
		}
		if (PortalGun.Instance != null) Hide(PortalGun.Instance.ViewmodelRenderer);
		return _hidden;
	}

	private bool IsVisible(Portal p)
	{
		var camPos = _mainCam.transform.position;
		var local = p.LocalPoint(camPos);
		// Behind the plane we only care while inside the tube (just after crossing, before the warp).
		if (local.z < -0.6f || (local.z < 0 && !p.InsideEllipse(local, 1.2f)))
			return false;
		var r = Mathf.Max(p.Size.x, p.Size.y);
		var planes = GeometryUtility.CalculateFrustumPlanes(_mainCam);
		return GeometryUtility.TestPlanesAABB(planes, new Bounds(p.transform.position, Vector3.one * r));
	}

	/// <summary>Viewport rect covering the portal (and its tube) on the player's screen; full screen if unsure.</summary>
	private Rect ScreenRect(Portal p)
	{
		var t = p.transform;
		var w = p.Size.x * 0.5f * 1.05f;
		var h = p.Size.y * 0.5f * 1.05f;
		float xmin = 1, ymin = 1, xmax = 0, ymax = 0;
		for (var i = 0; i < 8; i++)
		{
			var corner = t.TransformPoint(new Vector3((i & 1) == 0 ? -w : w, (i & 2) == 0 ? -h : h, (i & 4) == 0 ? 0.05f : -0.6f));
			var v = _mainCam.WorldToViewportPoint(corner);
			if (v.z <= _mainCam.nearClipPlane)
				return new Rect(0, 0, 1, 1);
			xmin = Mathf.Min(xmin, v.x);
			ymin = Mathf.Min(ymin, v.y);
			xmax = Mathf.Max(xmax, v.x);
			ymax = Mathf.Max(ymax, v.y);
		}
		const float pad = 0.01f;
		xmin = Mathf.Clamp01(xmin - pad);
		ymin = Mathf.Clamp01(ymin - pad);
		xmax = Mathf.Clamp01(xmax + pad);
		ymax = Mathf.Clamp01(ymax + pad);
		if (xmax - xmin < 0.002f || ymax - ymin < 0.002f)
			return new Rect(0, 0, 1, 1);
		return Rect.MinMaxRect(xmin, ymin, xmax, ymax);
	}

	/// <summary>Restricts a camera to a sub-rect of its target while keeping the full-screen projection.</summary>
	private static void Scissor(Camera cam, Rect r)
	{
		if (r.width >= 0.999f && r.height >= 0.999f)
			return;
		var full = cam.projectionMatrix;
		cam.rect = r;
		var m2 = Matrix4x4.TRS(new Vector3(1f / r.width - 1f, 1f / r.height - 1f, 0f), Quaternion.identity, new Vector3(1f / r.width, 1f / r.height, 1f));
		var m3 = Matrix4x4.TRS(new Vector3(-r.x * 2f / r.width, -r.y * 2f / r.height, 0f), Quaternion.identity, Vector3.one);
		cam.projectionMatrix = m3 * m2 * full;
	}

	private static Vector4 CameraSpacePlane(Camera cam, Vector3 pos, Vector3 normal)
	{
		var m = cam.worldToCameraMatrix;
		var cpos = m.MultiplyPoint(pos + normal * 0.01f);
		var cnormal = m.MultiplyVector(normal).normalized;
		return new Vector4(cnormal.x, cnormal.y, cnormal.z, -Vector3.Dot(cpos, cnormal));
	}

	/// <summary>The game draws stars and the sun's glow from a command buffer only on its own cameras.</summary>
	private void AddSkybox(Camera vc)
	{
		if (_skybox == null)
			_skybox = new CommandBuffer { name = "PortalSkybox" };
		vc.RemoveAllCommandBuffers();
		_skybox.Clear();
		var view = vc.worldToCameraMatrix;
		view.m03 = view.m13 = view.m23 = 0f;
		_skybox.SetViewProjectionMatrices(view, vc.projectionMatrix);
		_skybox.SetGlobalDepthBias(1E+09f, 0f);
		var list = SkyboxRenderer.activeSkyboxRenderers;
		for (var i = 0; i < list.Count; i++)
			if (list[i].shouldRender)
				_skybox.DrawRenderer(list[i].renderer, list[i].material);
		var evt = vc.actualRenderingPath == RenderingPath.DeferredShading ? CameraEvent.AfterLighting : CameraEvent.BeforeForwardOpaque;
		vc.AddCommandBuffer(evt, _skybox);
	}

	// --- travel -------------------------------------------------------------------------------------

	private void FixedUpdate()
	{
		var a = Portals[0];
		var b = Portals[1];
		var linked = a != null && b != null && a.IsOpen && b.IsOpen;
		for (var i = 0; i < 2; i++)
		{
			var p = Portals[i];
			if (p == null)
				continue;
			if (linked)
				Track(p);
			else
				ClearTracking(p);
		}
		var cd = new List<OWRigidbody>(_cooldown.Keys);
		foreach (var k in cd)
			if (k == null || Time.time > _cooldown[k])
				_cooldown.Remove(k);
	}

	private void Track(Portal p)
	{
		_seen.Clear();
		var t = p.transform;
		var radius = Mathf.Max(p.Size.x, p.Size.y) * 0.5f + 3f;
		var n = Physics.OverlapSphereNonAlloc(t.position, radius, _overlap, ~0, QueryTriggerInteraction.Ignore);
		for (var k = 0; k < n; k++)
		{
			var body = _overlap[k].GetAttachedOWRigidbody();
			if (body != null) _seen.Add(body);
		}
		// Fast things (the ship, the probe) can skip the sphere between two physics steps.
		var probe = Locator.GetProbe();
		var probeBody = probe != null && probe.IsLaunched() ? probe.GetOWRigidbody() : null;
		foreach (var extra in new[] { Locator.GetPlayerBody(), Locator.GetShipBody(), probeBody })
			if (extra != null && (extra.GetPosition() - t.position).sqrMagnitude < Sq(radius + extra.GetVelocity().magnitude * 0.1f + 10f))
				_seen.Add(extra);

		foreach (var body in _seen)
		{
			if (!CanTravel(body, p))
				continue;
			var key = (p, body);
			var local = p.LocalPoint(ReferencePoint(body));
			// Big bodies (the ship) touch the wall long before their centre reaches it: scale the zone with size.
			var r = BodyRadius(body);
			var inHole = p.InsideEllipse(local) && local.z > -3f - r && local.z < 2.5f + r;
			UpdateIgnore(key, body, p, inHole);
			if (_prevLocal.TryGetValue(key, out var prev) && prev.z >= 0f && local.z < 0f && !_cooldown.ContainsKey(body))
			{
				var tc = prev.z / (prev.z - local.z);
				var cross = Vector3.Lerp(prev, local, tc);
				if (p.InsideEllipse(cross))
				{
					Teleport(body, p);
					_prevLocal.Remove(key);
					continue;
				}
			}
			// While cooling down, keep the last pre-cooldown sample so a crossing in that window isn't lost.
			if (!_cooldown.ContainsKey(body) || !_prevLocal.ContainsKey(key))
				_prevLocal[key] = local;
		}
	}

	private static float Sq(float x) => x * x;

	private readonly Dictionary<OWRigidbody, float> _radius = new();

	/// <summary>Half the largest extent of the body's solid colliders (about 1 m for the player, 5+ for the ship).</summary>
	private float BodyRadius(OWRigidbody body)
	{
		if (_radius.TryGetValue(body, out var r))
			return r;
		var have = false;
		var b = new Bounds();
		foreach (var c in SolidColliders(body))
		{
			if (!c.enabled) continue;
			if (!have) { b = c.bounds; have = true; }
			else b.Encapsulate(c.bounds);
		}
		r = have ? Mathf.Max(b.extents.x, Mathf.Max(b.extents.y, b.extents.z)) : 1f;
		_radius[body] = r;
		PortalGunMod.Log($"body {body.name} radius {r:F1} m");
		return r;
	}

	private static bool CanTravel(OWRigidbody body, Portal p)
	{
		if (body == null || body == p.ParentBody || body == p.Linked.ParentBody || !body.gameObject.activeInHierarchy)
			return false;
		if (body.CompareTag("Probe") && (Locator.GetProbe() == null || !Locator.GetProbe().IsLaunched()))
			return false;
		if (body.CompareTag("Player"))
			return !PlayerState.IsInsideShip() && !PlayerState.IsAttached() && !PlayerState.InDreamWorld();
		if (body.IsKinematic() || body.IsSuspended())
			return false;
		// Planets and moons are kinematic; anything else free-floating can go.
		return true;
	}

	private Vector3 ReferencePoint(OWRigidbody body)
	{
		if (body.CompareTag("Player"))
			return _mainCam.transform.position;
		return body.GetWorldCenterOfMass();
	}

	private void UpdateIgnore((Portal, OWRigidbody) key, OWRigidbody body, Portal p, bool inHole)
	{
		var has = _ignoring.TryGetValue(key, out var cols);
		if (inHole)
		{
			if (!_walls.TryGetValue(key, out var walls))
				_walls[key] = walls = WallsFor(body, p);
			// Re-applied every step: Unity forgets IgnoreCollision when a collider is re-enabled
			// (the player toggles an anti-sinking collider while walking).
			cols = SolidColliders(body);
			_ignoring[key] = cols;
			SetIgnore(walls, cols, true);
		}
		else if (has)
		{
			if (_walls.TryGetValue(key, out var walls))
				SetIgnore(walls, cols, false);
			_ignoring.Remove(key);
			_walls.Remove(key);
		}
	}

	private readonly Dictionary<(Portal, OWRigidbody), Collider[]> _walls = new();

	/// <summary>
	/// The colliders the body may pass through while in this hole: the ones under the portal, plus, for a body
	/// bigger than the portal (the ship through a person-sized portal), the static ground around it within the
	/// body's reach, so it squeezes through instead of landing on the rim.
	/// </summary>
	private Collider[] WallsFor(OWRigidbody body, Portal p)
	{
		var r = BodyRadius(body);
		if (r <= Mathf.Min(p.Size.x, p.Size.y) * 0.5f)
			return p.Walls;
		var set = new HashSet<Collider>(p.Walls);
		foreach (var c in Physics.OverlapSphere(p.transform.position, r + 1f, OWLayerMask.physicalMask, QueryTriggerInteraction.Ignore))
			if (c.GetAttachedOWRigidbody() == p.ParentBody && p.ParentBody != null)
				set.Add(c);
		var arr = new Collider[set.Count];
		set.CopyTo(arr);
		PortalGunMod.Log($"{body.name} is bigger than {p.name}: passes through {arr.Length} ground colliders");
		return arr;
	}

	private static Collider[] SolidColliders(OWRigidbody body)
	{
		var rb = body.GetRigidbody();
		var list = new List<Collider>();
		foreach (var c in body.GetComponentsInChildren<Collider>(true))
			if (!c.isTrigger && c.GetComponentInParent<Rigidbody>() == rb)
				list.Add(c);
		return list.ToArray();
	}

	private static void SetIgnore(Collider[] walls, Collider[] cols, bool ignore)
	{
		if (walls == null || cols == null)
			return;
		foreach (var w in walls)
			if (w != null)
				foreach (var c in cols)
					if (c != null)
						Physics.IgnoreCollision(c, w, ignore);
	}

	/// <summary>
	/// True for a ground hit in the column behind a portal the body is passing through: the hole itself and
	/// whatever lies under it (caves, the back of the terrain). Nothing there may count as floor.
	/// </summary>
	public bool IsHoleHit(OWRigidbody body, Collider c, Vector3 point)
	{
		foreach (var kv in _ignoring)
		{
			var p = kv.Key.Item1;
			if (kv.Key.Item2 != body || p == null)
				continue;
			var local = p.LocalPoint(point);
			if (p.InsideEllipse(local, 1.1f) && local.z < 0.3f)
				return true;
		}
		return false;
	}

	/// <summary>
	/// The scout is a kinematic body that predicts its own impacts with a raycast and anchors where it lands, so the
	/// usual crossing test never sees it. Called when it is about to anchor: inside an open portal it goes through.
	/// </summary>
	public bool TryPassThrough(OWRigidbody body, Vector3 point)
	{
		foreach (var p in Portals)
		{
			if (p == null || p.Linked == null || !p.IsOpen || !p.Linked.IsOpen)
				continue;
			var local = p.LocalPoint(point);
			if (!p.InsideEllipse(local) || Mathf.Abs(local.z) > 0.6f)
				continue;
			// Just past the entry plane, so the mapped position is just in front of the exit.
			body.WarpToPositionRotation(point - p.transform.forward * 0.05f, body.transform.rotation);
			Teleport(body, p);
			return true;
		}
		return false;
	}

	public void Teleport(OWRigidbody body, Portal from)
	{
		var to = from.Linked;
		var pos = body.transform.position;
		var newPos = from.MapPoint(pos);
		var newRot = from.MapRotation(body.transform.rotation);
		var vFrom = from.ParentBody != null ? from.ParentBody.GetPointVelocity(pos) : Vector3.zero;
		var vTo = to.ParentBody != null ? to.ParentBody.GetPointVelocity(newPos) : Vector3.zero;
		var newVel = vTo + from.MapDirection(body.GetVelocity() - vFrom);
		var newAng = from.MapDirection(body.GetAngularVelocity());

		// The player walking inside the ship rides along with ShipBody's own warp; keep their speed too.
		var player = Locator.GetPlayerBody();
		var carryPlayer = body.CompareTag("Ship") && PlayerState.IsInsideShip() && !PlayerState.IsAttached();
		var playerVel = carryPlayer ? vTo + from.MapDirection(player.GetVelocity() - vFrom) : Vector3.zero;

		float pitch = 0f;
		var isPlayer = body.CompareTag("Player");
		if (isPlayer)
		{
			// Keep the eye exactly on its mapped point so the view doesn't jump when the body is righted.
			var camLocal = body.transform.InverseTransformPoint(_mainCam.transform.position);
			// A hair in front of the exit plane, so the next crossing test starts on the right side.
			var camMapped = from.MapPoint(_mainCam.transform.position) + to.transform.forward * 0.03f;
			newRot = UprightPlayer(from, to, camMapped, out pitch);
			newPos = camMapped - newRot * camLocal;
		}
		// The body may still be partly inside the exit wall: ignore it from this very step.
		UpdateIgnore((to, body), body, to, true);

		body.WarpToPositionRotation(newPos, newRot);
		if (isPlayer)
		{
			Locator.GetPlayerCameraController().SetDegreesY(pitch);
			Unground();
		}
		body.SetVelocity(newVel);
		body.SetAngularVelocity(newAng);
		if (carryPlayer)
			player.SetVelocity(playerVel);

		// Collisions with the entry wall stay ignored until the body leaves that hole; start tracking fresh.
		_cooldown[body] = Time.time + 0.15f;
		_prevLocal.Remove((to, body));
		Teleports++;
		PortalGun.Instance?.OnTeleported(body, from, to);
		PortalGunMod.Log($"teleport {body.name} {from.name}->{to.name} speed {newVel.magnitude:F1} m/s rel {(newVel - vTo).magnitude:F1}");
	}

	private static readonly System.Reflection.MethodInfo s_makeUngrounded = HarmonyLib.AccessTools.Method(typeof(PlayerCharacterController), "MakeUngrounded");
	private static readonly System.Reflection.FieldInfo s_wasGrounded = HarmonyLib.AccessTools.Field(typeof(PlayerCharacterController), "_wasGrounded");
	private static readonly System.Reflection.FieldInfo s_lastJump = HarmonyLib.AccessTools.Field(typeof(PlayerCharacterController), "_lastJumpTime");

	/// <summary>
	/// The controller still thinks it stands on the entry side and would snap the player down onto whatever its
	/// ground cast finds under the exit (on Timber Hearth: the caves). Drop the grounded state and hold off ground
	/// snapping for half a second, the same window the game uses after a jump.
	/// </summary>
	private static void Unground()
	{
		var ctrl = Locator.GetPlayerController();
		if (ctrl == null)
			return;
		if (ctrl.IsGrounded())
			s_makeUngrounded.Invoke(ctrl, null);
		s_wasGrounded.SetValue(ctrl, false);
		s_lastJump.SetValue(ctrl, Time.time);
	}

	/// <summary>
	/// Like Portal 2: the player comes out upright for the gravity at the exit, looking where the mapped view looks.
	/// (Applying the raw rotation leaves them upside down after a floor-to-floor trip, and the game rights them slowly.)
	/// </summary>
	private Quaternion UprightPlayer(Portal from, Portal to, Vector3 newPos, out float pitch)
	{
		var cam = _mainCam.transform;
		var fwd = from.MapDirection(cam.forward);
		var bodyUpMapped = from.MapDirection(Locator.GetPlayerBody().transform.up);
		var up = bodyUpMapped;
		var grav = to.ParentBody != null ? to.ParentBody.GetAttachedGravityVolume() : null;
		if (grav != null)
		{
			var g = grav.CalculateForceAccelerationAtPoint(newPos);
			if (g.sqrMagnitude > 1e-4f) up = -g.normalized;
		}
		else if (Locator.GetPlayerForceDetector() != null && Locator.GetPlayerForceDetector().GetForceAcceleration().sqrMagnitude > 1e-4f)
			up = -Locator.GetPlayerForceDetector().GetForceAcceleration().normalized;
		var flat = Vector3.ProjectOnPlane(fwd, up);
		if (flat.sqrMagnitude < 1e-3f)
			flat = Vector3.ProjectOnPlane(from.MapDirection(Locator.GetPlayerBody().transform.forward), up);
		if (flat.sqrMagnitude < 1e-3f)
			flat = Vector3.ProjectOnPlane(-bodyUpMapped, up);
		var rot = Quaternion.LookRotation(flat.normalized, up);
		pitch = Mathf.Clamp(90f - Vector3.Angle(up, fwd), -80f, 80f);
		return rot;
	}

	private void LateUpdate()
	{
		// The camera can cross the plane between physics steps; warp the player before that frame renders.
		var player = Locator.GetPlayerBody();
		if (player == null)
			return;
		for (var i = 0; i < 2; i++)
		{
			var p = Portals[i];
			if (p == null || p.Linked == null || !p.IsOpen || !p.Linked.IsOpen || !CanTravel(player, p) || _cooldown.ContainsKey(player))
				continue;
			var key = (p, player);
			if (!_prevLocal.TryGetValue(key, out var prev))
				continue;
			var local = p.LocalPoint(_mainCam.transform.position);
			if (prev.z >= 0f && local.z < 0f)
			{
				var cross = Vector3.Lerp(prev, local, prev.z / (prev.z - local.z));
				if (p.InsideEllipse(cross))
				{
					Teleport(player, p);
					_prevLocal.Remove(key);
					return;
				}
			}
		}
	}
}
