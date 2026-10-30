using System;
using OWML.Common;
using UnityEngine;
using UnityEngine.Rendering;

namespace BlockCraft;

/// <summary>
/// Paints the guest's picture into the host's world, where the host says its "screen" is.
///
/// Two stencil passes, exactly as the portal gun example proves out with the game's own UI/Default
/// shader (a mod cannot compile shaders at runtime):
///
/// 1. a depth-tested quad over the placement surface writes a stencil ref where it is *visible*, so a
///    rock between the camera and the screen hides the picture the same way it hides a real object;
/// 2. a screen-aligned quad over the whole view paints the guest's texture only where that ref is set.
///
/// The guest's colour is uploaded from the POSIX mapping FrameReader reads. Depth from the guest is not
/// used for the picture itself: the host's own depth buffer already occludes the quad, which is what the
/// first slice is for. (Guest depth is exported and read; using it for per-pixel occlusion of guest
/// geometry drawn into the host is later work.)
/// </summary>
public sealed class Compositor : MonoBehaviour
{
	public static Compositor Instance;

	/// <summary>Stencil ref for the screen surface. Distinct from anything the portal gun example uses.</summary>
	private const int ScreenStencilRef = 61;
	private const int StencilQueue = 2990;
	private const int CompositeQueue = 2991;

	public FrameReader Reader;
	public HostLink Link;

	/// <summary>The mapping to read; set from the handshake when the guest announces a different name.</summary>
	public string ShmName = "blockcraft-frame";

	public MeshRenderer StencilRenderer;
	public MeshRenderer CompositeRenderer;

	private Material _stencilMat;
	private Material _compositeMat;
	private Texture2D _texture;
	private Camera _mainCam;
	private FrameReader.Frame _frame = new();

	/// <summary>Where in the world the picture is shown. Set by the dev bridge / ground placement.</summary>
	public Vector3 ScreenPosition = new(0f, 0f, 0f);
	public Vector3 ScreenNormal = Vector3.forward;
	public float ScreenWidth = 3.2f;
	public float ScreenHeight = 1.8f;

	public long FrameReads;
	public long FrameMisses;
	public long LastGuestFrame;
	public float LastFrameAgeMs = -1f;

	private float _lastTextureUpload = -1f;
	private float _lastPullTime;

	public static Compositor Create(HostLink link)
	{
		var go = new GameObject("BlockCraftCompositor");
		// The compositor is created while the SolarSystem scene is loading. Without this it is destroyed
		// by that same load and never draws a frame (the mod logged "passthrough up" and then nothing).
		UnityEngine.Object.DontDestroyOnLoad(go);
		var c = go.AddComponent<Compositor>();
		c.Link = link;
		Instance = c;
		return c;
	}

	private void Awake()
	{
		Instance = this;
	}

	private void Start()
	{
		_mainCam = Locator.GetPlayerCamera()?.mainCamera;
		if (_mainCam == null)
		{
			BlockCraftMod.Log("compositor: no player camera yet, will retry", MessageType.Warning);
		}
		BuildScreen();
		Camera.onPreCull += OnPreCull;
	}

	private void OnDestroy()
	{
		Camera.onPreCull -= OnPreCull;
		if (_texture != null) Destroy(_texture);
		if (StencilRenderer != null) Destroy(StencilRenderer.gameObject);
		if (CompositeRenderer != null) Destroy(CompositeRenderer.gameObject);
		if (Instance == this) Instance = null;
		Reader?.Dispose();
	}

	// --- scene objects ------------------------------------------------------------------------------

	private void BuildScreen()
	{
		if (StencilRenderer == null)
		{
			var go = new GameObject("BlockCraftScreenStencil");
			go.transform.SetParent(transform, false);
			go.AddComponent<MeshFilter>().sharedMesh = Quad();
			StencilRenderer = go.AddComponent<MeshRenderer>();
			StencilRenderer.shadowCastingMode = ShadowCastingMode.Off;
			StencilRenderer.receiveShadows = false;
		}

		if (CompositeRenderer == null)
		{
			var go = new GameObject("BlockCraftScreenComposite");
			go.transform.SetParent(_mainCam != null ? _mainCam.transform : transform, false);
			go.AddComponent<MeshFilter>().sharedMesh = ScreenQuad();
			CompositeRenderer = go.AddComponent<MeshRenderer>();
			CompositeRenderer.shadowCastingMode = ShadowCastingMode.Off;
			CompositeRenderer.receiveShadows = false;
		}

		StencilRenderer.sharedMaterial = StencilWriter();
		CompositeRenderer.sharedMaterial = Composite();
	}

	private static Mesh Quad()
	{
		var m = new Mesh();
		m.vertices = new[]
		{
			new Vector3(-0.5f, -0.5f, 0f), new Vector3(0.5f, -0.5f, 0f),
			new Vector3(0.5f, 0.5f, 0f), new Vector3(-0.5f, 0.5f, 0f)
		};
		m.uv = new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(1, 1), new Vector2(0, 1) };
		m.triangles = new[] { 0, 2, 1, 0, 3, 2 };
		m.bounds = new Bounds(Vector3.zero, Vector3.one * 10f);
		return m;
	}

	private static Mesh ScreenQuad()
	{
		var m = new Mesh();
		m.vertices = new[]
		{
			new Vector3(-1, -1, 0), new Vector3(1, -1, 0), new Vector3(1, 1, 0), new Vector3(-1, 1, 0)
		};
		m.uv = new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(1, 1), new Vector2(0, 1) };
		m.triangles = new[] { 0, 2, 1, 0, 3, 2 };
		m.bounds = new Bounds(Vector3.zero, Vector3.one * 1000f);
		return m;
	}

	// --- materials (the game's own UI/Default shader, as the portal gun example does) ---------------

	private Material StencilWriter()
	{
		var ui = Shader.Find("UI/Default");
		if (ui == null)
		{
			BlockCraftMod.Log("compositor: UI/Default shader missing", MessageType.Error);
			return null;
		}

		_stencilMat = new Material(ui) { name = "bc_stencil" };
		_stencilMat.SetFloat("_StencilComp", (float)CompareFunction.Always);
		_stencilMat.SetFloat("_Stencil", ScreenStencilRef);
		_stencilMat.SetFloat("_StencilOp", (float)StencilOp.Replace);
		_stencilMat.SetFloat("_StencilWriteMask", 255);
		_stencilMat.SetFloat("_StencilReadMask", 255);
		_stencilMat.SetFloat("_ColorMask", 0);
		// depth-tested, so OW terrain in front of the screen occludes it
		_stencilMat.SetFloat("unity_GUIZTestMode", (float)CompareFunction.LessEqual);
		_stencilMat.renderQueue = StencilQueue;
		return _stencilMat;
	}

	private Material Composite()
	{
		var ui = Shader.Find("UI/Default");
		_compositeMat = new Material(ui) { name = "bc_composite", mainTexture = _texture, color = Color.white };
		_compositeMat.SetFloat("_StencilComp", (float)CompareFunction.Equal);
		_compositeMat.SetFloat("_Stencil", ScreenStencilRef);
		_compositeMat.SetFloat("_StencilOp", (float)StencilOp.Keep);
		_compositeMat.SetFloat("_StencilWriteMask", 0);
		_compositeMat.SetFloat("_StencilReadMask", 255);
		_compositeMat.SetFloat("_ColorMask", 15);
		// the screen quad is already depth-tested, so this pass is not
		_compositeMat.SetFloat("unity_GUIZTestMode", (float)CompareFunction.Always);
		_compositeMat.renderQueue = CompositeQueue;
		return _compositeMat;
	}

	// --- frame <- guest -----------------------------------------------------------------------------

	/// <summary>Open or reopen the guest's mapping; safe to call when already open.</summary>
	public bool EnsureReader()
	{
		if (Reader != null) return true;
		try
		{
			Reader = FrameReader.Open(ShmName);
			if (!Reader.IsCompatible)
			{
				Reader.Dispose();
				Reader = null;
				return false;
			}

			BlockCraftMod.Log($"frame mapping {ShmName} open: {Reader.MaxWidth}x{Reader.MaxHeight} max, " +
				$"pid {Reader.GuestPid}");
			return true;
		}
		catch (Exception e)
		{
			BlockCraftMod.Log("frame mapping not open: " + e.Message);
			return false;
		}
	}

	/// <summary>Pull the newest guest frame into the texture (render thread, once per frame).</summary>
	private bool Pull()
	{
		if (!EnsureReader()) return false;
		if (!Reader.TryRead(_frame))
		{
			FrameMisses++;
			return false;
		}

		FrameReads++;
		LastGuestFrame = _frame.GuestFrame;
		// The guest stamps capture/publish on its own monotonic clock, which the contract says never to
		// compare across processes; treat a frame as stale when *we* have not read it for a while instead.
		LastFrameAgeMs = (float)(Time.realtimeSinceStartup - _lastPullTime) * 1000f;
		_lastPullTime = Time.realtimeSinceStartup;

		if (_texture == null || _texture.width != _frame.Width || _texture.height != _frame.Height)
		{
			if (_texture != null) Destroy(_texture);
			// RGBA32, no mipmaps: the guest picture is shown at roughly its own resolution
			_texture = new Texture2D(_frame.Width, _frame.Height, TextureFormat.RGBA32, false)
			{
				name = "bc_guest",
				wrapMode = TextureWrapMode.Clamp,
				filterMode = FilterMode.Bilinear
			};
			if (_compositeMat != null) _compositeMat.mainTexture = _texture;
		}

		_texture.LoadRawTextureData(_frame.Colour);
		_texture.Apply(false, false);
		_lastTextureUpload = Time.unscaledTime;
		return true;
	}

	// --- render -------------------------------------------------------------------------------------

	private void OnPreCull(Camera cam)
	{
		if (cam != _mainCam)
		{
			_mainCam ??= Locator.GetPlayerCamera()?.mainCamera;
			return;
		}

		var live = Link != null && Link.Connected && Pull();
		if (StencilRenderer != null) StencilRenderer.enabled = live;
		if (CompositeRenderer != null) CompositeRenderer.enabled = live;
		if (!live) return;

		// the screen surface: sized and placed by whatever set it (dev bridge, or a real surface later)
		var t = StencilRenderer.transform;
		t.SetPositionAndRotation(ScreenPosition, Quaternion.LookRotation(ScreenNormal, Vector3.up));
		t.localScale = new Vector3(ScreenWidth, ScreenHeight, 1f);

		// the composite is screen-aligned, just past the near plane (as the portal gun example does)
		var d = _mainCam.nearClipPlane * 1.05f;
		var hh = d * Mathf.Tan(_mainCam.fieldOfView * 0.5f * Mathf.Deg2Rad);
		var ct = CompositeRenderer.transform;
		ct.localPosition = new Vector3(0, 0, d);
		ct.localRotation = Quaternion.identity;
		ct.localScale = new Vector3(hh * _mainCam.aspect * 1.02f, hh * 1.02f, 1f);
	}

	/// <summary>Place the picture where the player is looking, a few metres ahead (dev/testing).</summary>
	public void PlaceInFront(float distance = 6f)
	{
		var cam = _mainCam != null ? _mainCam : Locator.GetPlayerCamera()?.mainCamera;
		if (cam == null) return;
		ScreenPosition = cam.transform.position + cam.transform.forward * distance;
		ScreenNormal = -cam.transform.forward;
		BlockCraftMod.Log($"screen placed at {ScreenPosition} facing {ScreenNormal}");
	}

	public void SetSize(float width, float height)
	{
		ScreenWidth = width;
		ScreenHeight = height;
	}

	public string Status()
	{
		if (Link == null || !Link.Connected) return "no guest attached";
		if (Reader == null) return "guest attached, mapping not open";
		return $"frames {FrameReads}, misses {FrameMisses}, guest frame {LastGuestFrame}, " +
			$"size {_frame.Width}x{_frame.Height}, camera-born {Reader.GuestPid == 0}";
	}
}
