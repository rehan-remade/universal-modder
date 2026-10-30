using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace OWPortalGun;

/// <summary>
/// Materials built from shaders the game build already contains (a mod can't compile shaders at runtime).
/// UI/Default is always included and exposes stencil and colour-mask properties, which is all the portal
/// effect needs: one pass writes the portal's shape into the stencil buffer, a second pass paints the
/// portal camera's picture only where that stencil is set.
/// </summary>
public static class Materials
{
	public static Shader Lit, Ui, Sprite, Additive;
	public static Material GameViewmodel, GameViewmodelPrepass;

	/// <summary>The game's own viewmodel materials (fixed viewmodel FOV, never clip into walls), from the signalscope.</summary>
	public static void InitFromGame(ToolModeSwapper swapper)
	{
		if (GameViewmodel != null || swapper == null || swapper.GetSignalScope() == null)
			return;
		foreach (var r in swapper.GetSignalScope().GetComponentsInChildren<Renderer>(true))
		{
			var m = r.sharedMaterial;
			if (m == null || m.shader == null) continue;
			if (m.shader.name.EndsWith("View Model Prepass")) GameViewmodelPrepass = m;
			else if (m.shader.name.Contains("View Model")) GameViewmodel = m;
		}
		PortalGunMod.Log($"game viewmodel materials: {GameViewmodel?.shader.name} / {GameViewmodelPrepass?.shader.name}");
	}

	public static void Init()
	{
		Ui = Shader.Find("UI/Default");
		Sprite = Shader.Find("Sprites/Default");
		Lit = Find("Standard", "Legacy Shaders/Bumped Specular", "Legacy Shaders/Diffuse");
		Additive = Find("Legacy Shaders/Particles/Additive", "Particles/Additive", "Mobile/Particles/Additive",
			"Particles/Standard Unlit");
		PortalGunMod.Log($"shaders: lit={Name(Lit)} ui={Name(Ui)} sprite={Name(Sprite)} additive={Name(Additive)}");
	}

	private static Shader Find(params string[] names)
	{
		foreach (var n in names)
		{
			var s = Shader.Find(n);
			if (s != null && s.isSupported)
				return s;
		}
		return null;
	}

	private static string Name(Shader s) => s == null ? "MISSING" : s.name;

	public static Material ForGun(GunAssets assets, string name)
	{
		assets.Textures.TryGetValue(name, out var tex);
		if (GameViewmodel != null)
		{
			var vm = new Material(GameViewmodel) { name = "pg_" + name, mainTexture = tex };
			vm.DisableKeyword("_ALPHATEST_ON");
			vm.DisableKeyword("_METALLICGLOSSMAP");
			vm.DisableKeyword("_EMISSION");
			vm.SetFloat("_Cutoff", 0f);
			vm.SetTexture("_MetallicGlossMap", null);
			vm.SetTexture("_EmissionMap", null);
			vm.SetColor("_EmissionColor", Color.black);
			vm.SetColor("_Color", Color.white);
			vm.SetFloat("_Metallic", 0f);
			vm.SetFloat("_Glossiness", name.Contains("glass") ? 0.9f : 0.5f);
			vm.SetFloat("_GlossMapScale", 0.5f);
			if (assets.Textures.TryGetValue("v_portalgun_normal", out var vn) && !name.Contains("glass"))
			{
				vm.SetTexture("_BumpMap", vn);
				vm.EnableKeyword("_NORMALMAP");
			}
			else
			{
				vm.SetTexture("_BumpMap", null);
				vm.DisableKeyword("_NORMALMAP");
			}
			return vm;
		}
		if (name.Contains("glass"))
		{
			var glass = new Material(Additive != null ? Additive : Sprite) { name = "pg_glass", mainTexture = tex };
			glass.color = Additive != null ? new Color(0.35f, 0.4f, 0.45f, 0.5f) : new Color(0.6f, 0.7f, 0.8f, 0.25f);
			glass.renderQueue = 3100;
			return glass;
		}
		var m = new Material(Lit != null ? Lit : Sprite) { name = "pg_" + name, mainTexture = tex };
		if (Lit != null && Lit.name == "Standard")
		{
			m.SetFloat("_Glossiness", 0.55f);
			m.SetFloat("_Metallic", 0f);
			if (assets.Textures.TryGetValue("v_portalgun_normal", out var nrm))
			{
				m.SetTexture("_BumpMap", nrm);
				m.EnableKeyword("_NORMALMAP");
			}
		}
		return m;
	}

	public static Material Unlit(Texture tex, Color color, bool additive, int queue)
	{
		var m = new Material(additive && Additive != null ? Additive : Sprite) { mainTexture = tex, color = color };
		m.renderQueue = queue;
		return m;
	}

	/// <summary>Writes `stencilRef` where the portal surface is visible (depth-tested, no colour).</summary>
	public static Material StencilWriter(int stencilRef, int queue)
	{
		var m = new Material(Ui) { name = "pg_stencil_" + stencilRef };
		m.SetFloat("_StencilComp", (float)CompareFunction.Always);
		m.SetFloat("_Stencil", stencilRef);
		m.SetFloat("_StencilOp", (float)StencilOp.Replace);
		m.SetFloat("_StencilWriteMask", 255);
		m.SetFloat("_StencilReadMask", 255);
		m.SetFloat("_ColorMask", 0);
		m.SetFloat("unity_GUIZTestMode", (float)CompareFunction.LessEqual);
		m.renderQueue = queue;
		return m;
	}

	/// <summary>Paints `tex` (screen-aligned) only where the stencil equals `stencilRef`.</summary>
	public static Material StencilComposite(Texture tex, int stencilRef, int queue)
	{
		var m = new Material(Ui) { name = "pg_composite_" + stencilRef, mainTexture = tex, color = Color.white };
		m.SetFloat("_StencilComp", (float)CompareFunction.Equal);
		m.SetFloat("_Stencil", stencilRef);
		m.SetFloat("_StencilOp", (float)StencilOp.Keep);
		m.SetFloat("_StencilWriteMask", 0);
		m.SetFloat("_StencilReadMask", 255);
		m.SetFloat("_ColorMask", 15);
		m.SetFloat("unity_GUIZTestMode", (float)CompareFunction.Always);
		m.renderQueue = queue;
		return m;
	}

	private static readonly Dictionary<string, Texture2D> s_generated = new();

	/// <summary>Elliptical ring for the portal rim, tinted from Portal 2's colour ramp.</summary>
	public static Texture2D RimTexture(GunAssets assets, bool orange)
	{
		var key = orange ? "rim_orange" : "rim_blue";
		if (s_generated.TryGetValue(key, out var cached))
			return cached;
		assets.Textures.TryGetValue(orange ? "portal-orange-color" : "portal-blue-color", out var ramp);
		assets.Textures.TryGetValue("noise-blur", out var noise);
		const int n = 256;
		var tex = new Texture2D(n, n, TextureFormat.RGBA32, true) { name = key, wrapMode = TextureWrapMode.Clamp };
		var px = new Color[n * n];
		for (var y = 0; y < n; y++)
			for (var x = 0; x < n; x++)
			{
				var u = (x + 0.5f) / n * 2f - 1f;
				var v = (y + 0.5f) / n * 2f - 1f;
				var r = Mathf.Sqrt(u * u + v * v); // the quad is scaled to the ellipse, so r = 1 is the edge
				var nz = noise != null ? noise.GetPixelBilinear(x / (float)n * 2f, y / (float)n * 2f).r : 0.5f;
				var edge = 0.86f + 0.04f * nz;
				var a = Mathf.Clamp01(1f - Mathf.Abs(r - edge) / 0.075f);
				a = a * a * (3f - 2f * a);
				var inner = Mathf.Clamp01((r - 0.6f) / (edge - 0.6f));
				var glow = r < edge ? 0.25f * inner * inner : 0f;
				var c = ramp != null ? ramp.GetPixelBilinear(Mathf.Clamp01(0.35f + 0.6f * a), 0.5f)
					: orange ? new Color(1f, 0.55f, 0.1f) : new Color(0.1f, 0.5f, 1f);
				var alpha = Mathf.Clamp01(a + glow);
				px[y * n + x] = new Color(Mathf.Clamp01(c.r * 1.6f + a * 0.3f), Mathf.Clamp01(c.g * 1.6f + a * 0.3f),
					Mathf.Clamp01(c.b * 1.6f + a * 0.3f), alpha);
			}
		tex.SetPixels(px);
		tex.Apply(true);
		s_generated[key] = tex;
		return tex;
	}
}
