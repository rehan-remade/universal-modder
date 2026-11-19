using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace OWPortalGun;

/// <summary>
/// One portal. Its transform sits on the surface with +Z = surface normal (out of the wall) and +Y = portal up,
/// parented to whatever it hit so it rides planets, islands and the ship.
/// </summary>
public class Portal : MonoBehaviour
{
	public const int StencilBlue = 64, StencilOrange = 128;
	private const float OpenTime = 0.22f;
	private const float SurfaceOffset = 0.02f;
	private const float TubeDepth = 0.6f;

	public int Color;               // 0 blue, 1 orange
	public Vector2 Size;            // full width, height in metres
	public Collider Wall;           // the collider the shot hit (the portal rides it)
	public Collider[] Walls;        // every collider under the portal (ignored by travellers in the hole)
	public OWRigidbody ParentBody;  // body the portal rides (for relative velocity)
	public Portal Linked;

	public Material StencilMat, CompositeMat;
	public RenderTexture Texture;
	public Camera ViewCamera;
	public MeshRenderer StencilRenderer, ClosedRenderer, RimRenderer;
	public AudioSource Audio;

	private float _openT;
	private bool _closing;

	public int StencilRef => Color == 0 ? StencilBlue : StencilOrange;
	public bool IsOpen => !_closing && _openT >= 1f;

	public static Portal Create(GunAssets assets, int color, Vector2 size, Vector3 pos, Quaternion rot, Collider wall)
	{
		var go = new GameObject(color == 0 ? "PortalBlue" : "PortalOrange");
		var parent = PickParent(wall, out var body);
		go.transform.SetPositionAndRotation(pos, rot);
		go.transform.SetParent(parent, true);
		FixScale(go.transform);
		var p = go.AddComponent<Portal>();
		p.Color = color;
		p.Size = size;
		p.Wall = wall;
		p.ParentBody = body;
		p.Build(assets);
		return p;
	}

	/// <summary>Collider transform when it isn't skewed, else its rigidbody, so the portal never shears.</summary>
	private static Transform PickParent(Collider wall, out OWRigidbody body)
	{
		body = wall != null ? wall.GetAttachedOWRigidbody() : null;
		if (wall == null)
			return null;
		var s = wall.transform.lossyScale;
		var uniform = Mathf.Abs(s.x - s.y) < 1e-3f * Mathf.Abs(s.x) && Mathf.Abs(s.x - s.z) < 1e-3f * Mathf.Abs(s.x);
		if (uniform)
			return wall.transform;
		return body != null ? body.transform : wall.transform.root;
	}

	private static void FixScale(Transform t)
	{
		var ls = t.lossyScale;
		var l = t.localScale;
		t.localScale = new Vector3(l.x / ls.x, l.y / ls.y, l.z / ls.z);
	}

	private void Build(GunAssets assets)
	{
		var w = Size.x * 0.5f;
		var h = Size.y * 0.5f;
		_visual = new GameObject("visual").transform;
		_visual.SetParent(transform, false);

		// Rim: a quad whose texture has its ring at r = 0.88, scaled so the ring lands on the ellipse.
		var rim = new GameObject("rim");
		rim.transform.SetParent(_visual, false);
		rim.transform.localPosition = new Vector3(0, 0, SurfaceOffset * 1.5f);
		RimRenderer = AddMesh(rim, Quad(w / 0.88f, h / 0.88f),
			Materials.Unlit(Materials.RimTexture(assets, Color == 1), UnityEngine.Color.white, false, 3001));

		// Closed surface (no partner yet): Portal 2's swirling static, tinted.
		var closed = new GameObject("closed");
		closed.transform.SetParent(_visual, false);
		closed.transform.localPosition = new Vector3(0, 0, SurfaceOffset);
		assets.Textures.TryGetValue("noise-blur", out var noise);
		var tint = Color == 0 ? new Color(0.15f, 0.45f, 1f, 0.9f) : new Color(1f, 0.5f, 0.1f, 0.9f);
		ClosedRenderer = AddMesh(closed, Ellipse(w, h, 64), Materials.Unlit(noise, tint, false, 3000));

		// Open surface: ellipse + a short tube behind it, so a camera that has just crossed the plane
		// still sees the far side instead of the inside of the wall.
		var surf = new GameObject("surface");
		surf.transform.SetParent(_visual, false);
		surf.transform.localPosition = new Vector3(0, 0, SurfaceOffset);
		StencilMat = Materials.StencilWriter(StencilRef, 2990);
		StencilRenderer = AddMesh(surf, EllipseTube(w, h, TubeDepth, 64), StencilMat);
		StencilRenderer.enabled = false;


		Audio = gameObject.AddComponent<AudioSource>();
		Audio.spatialBlend = 1f;
		Audio.minDistance = 2f;
		Audio.maxDistance = 80f;
		Audio.rolloffMode = AudioRolloffMode.Linear;
		Audio.playOnAwake = false;

		_visual.localScale = new Vector3(0.01f, 0.01f, 1f);
	}

	private Transform _visual;

	private static MeshRenderer AddMesh(GameObject go, Mesh mesh, Material mat)
	{
		go.AddComponent<MeshFilter>().sharedMesh = mesh;
		var r = go.AddComponent<MeshRenderer>();
		r.sharedMaterial = mat;
		r.shadowCastingMode = ShadowCastingMode.Off;
		r.receiveShadows = false;
		return r;
	}

	public void Close()
	{
		_closing = true;
	}

	private void Update()
	{
		if (_closing)
		{
			_openT -= Time.deltaTime / (OpenTime * 0.7f);
			if (_openT <= 0f)
			{
				Destroy(gameObject);
				return;
			}
		}
		else if (_openT < 1f)
			_openT = Mathf.Min(1f, _openT + Time.deltaTime / OpenTime);
		var s = Mathf.SmoothStep(0.01f, 1f, _openT);
		_visual.localScale = new Vector3(s, s, 1f);

		var linked = Linked != null && Linked.IsOpen && IsOpen;
		ClosedRenderer.enabled = !linked;
		// The rim gently breathes, like Portal 2's.
		RimRenderer.sharedMaterial.color = new Color(1f, 1f, 1f, 0.85f + 0.15f * Mathf.Sin(Time.time * 6f + Color));
	}

	// --- geometry ------------------------------------------------------------------------------------

	public bool InsideEllipse(Vector3 local, float scale = 1f)
	{
		var a = Size.x * 0.5f * scale;
		var b = Size.y * 0.5f * scale;
		return local.x * local.x / (a * a) + local.y * local.y / (b * b) <= 1f;
	}

	/// <summary>Through-the-portal transform: in front of this portal → in front of the linked one.</summary>
	public static readonly Quaternion Flip = Quaternion.AngleAxis(180f, Vector3.up);

	public Vector3 MapPoint(Vector3 world) => Linked.transform.TransformPoint(Flip * transform.InverseTransformPoint(world));

	public Vector3 MapDirection(Vector3 dir) => Linked.transform.rotation * (Flip * (Quaternion.Inverse(transform.rotation) * dir));

	public Quaternion MapRotation(Quaternion rot) => Linked.transform.rotation * Flip * Quaternion.Inverse(transform.rotation) * rot;

	public Vector3 LocalPoint(Vector3 world) => transform.InverseTransformPoint(world);

	private static Mesh Quad(float w, float h)
	{
		var m = new Mesh();
		m.vertices = new[] { new Vector3(-w, -h, 0), new Vector3(w, -h, 0), new Vector3(w, h, 0), new Vector3(-w, h, 0) };
		m.uv = new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(1, 1), new Vector2(0, 1) };
		m.triangles = new[] { 0, 2, 1, 0, 3, 2, 0, 1, 2, 0, 2, 3 };
		m.RecalculateBounds();
		return m;
	}

	private static Mesh Ellipse(float w, float h, int n)
	{
		var v = new List<Vector3> { Vector3.zero };
		var uv = new List<Vector2> { new(0.5f, 0.5f) };
		var t = new List<int>();
		for (var i = 0; i < n; i++)
		{
			var a = i * Mathf.PI * 2f / n;
			v.Add(new Vector3(Mathf.Cos(a) * w, Mathf.Sin(a) * h, 0));
			uv.Add(new Vector2(0.5f + 0.5f * Mathf.Cos(a) * w / 2f, 0.5f + 0.5f * Mathf.Sin(a) * h / 2f));
			var j = i + 1;
			var k = (i + 1) % n + 1;
			t.AddRange(new[] { 0, k, j, 0, j, k });
		}
		var m = new Mesh();
		m.SetVertices(v);
		m.SetUVs(0, uv);
		m.SetTriangles(t, 0);
		m.RecalculateBounds();
		return m;
	}

	private static Mesh EllipseTube(float w, float h, float depth, int n)
	{
		var v = new List<Vector3> { Vector3.zero, new(0, 0, -depth) };
		var t = new List<int>();
		for (var i = 0; i < n; i++)
		{
			var a = i * Mathf.PI * 2f / n;
			var x = Mathf.Cos(a) * w;
			var y = Mathf.Sin(a) * h;
			v.Add(new Vector3(x, y, 0));
			v.Add(new Vector3(x, y, -depth));
		}
		for (var i = 0; i < n; i++)
		{
			var f0 = 2 + i * 2;
			var b0 = f0 + 1;
			var f1 = 2 + (i + 1) % n * 2;
			var b1 = f1 + 1;
			t.AddRange(new[] { 0, f1, f0 });       // front cap
			t.AddRange(new[] { 1, b0, b1 });       // back cap
			t.AddRange(new[] { f0, f1, b1, f0, b1, b0 }); // tube wall
		}
		var m = new Mesh();
		m.SetVertices(v);
		m.SetTriangles(t, 0);
		m.RecalculateBounds();
		return m;
	}
}
