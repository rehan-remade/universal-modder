using System;
using UnityEngine;

namespace BlockCraft;

/// <summary>
/// Minecraft-lookalike block textures drawn in code at load: 16x16, point filtered, per-face.
/// Nothing here is copied from Minecraft or Outer Wilds assets; palettes are the genre's
/// public look (green grass top, brown dirt) re-drawn pixel by pixel with a fixed seed.
/// </summary>
public enum BlockType { Grass, Dirt, Stone, Log, Planks, Leaves }

public static class BlockTextures
{
	public static readonly string[] Names = { "Grass", "Dirt", "Stone", "Oak Log", "Oak Planks", "Leaves" };

	private static Material[,] _mats; // [type, face] face: 0 top, 1 bottom, 2 side
	private static Mesh _mesh;
	private static Material _ghostOk, _ghostBad, _crack;

	public static Mesh BlockMesh => _mesh ??= BuildMesh();

	// MeshRenderer material order for our mesh submeshes: 0 side, 1 top, 2 bottom.
	public static Material[] SubmeshMaterialsFor(BlockType t)
	{
		Init();
		return new[] { _mats[(int)t, 2], _mats[(int)t, 0], _mats[(int)t, 1] };
	}

	public static Material GhostOk => _ghostOk ??= Ghost(new Color(0.45f, 1f, 0.45f, 0.4f));
	public static Material GhostBad => _ghostBad ??= Ghost(new Color(1f, 0.35f, 0.3f, 0.4f));
	public static Material Crack => _crack ??= Ghost(new Color(0f, 0f, 0f, 0.55f));

	private static Material Ghost(Color c)
	{
		var m = new Material(Shader.Find("Standard")) { name = "blockcraft_ghost" };
		m.color = c;
		m.SetFloat("_Mode", 3f); // transparent
		m.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
		m.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
		m.SetInt("_ZWrite", 0);
		m.DisableKeyword("_ALPHATEST_ON");
		m.EnableKeyword("_ALPHABLEND_ON");
		m.renderQueue = 3000;
		return m;
	}

	private static void Init()
	{
		if (_mats != null) return;
		_mats = new Material[Names.Length, 3];
		var lit = Shader.Find("Standard");
		for (var i = 0; i < Names.Length; i++)
		{
			var t = (BlockType)i;
			_mats[i, 0] = Make(lit, t, Face.Top);
			_mats[i, 1] = Make(lit, t, Face.Bottom);
			_mats[i, 2] = Make(lit, t, Face.Side);
		}
	}

	private enum Face { Top, Bottom, Side }

	private static Material Make(Shader lit, BlockType t, Face f)
	{
		var tex = new Texture2D(16, 16, TextureFormat.RGBA32, false)
		{
			name = $"blockcraft_{t}_{f}",
			filterMode = FilterMode.Point,
			wrapMode = TextureWrapMode.Clamp
		};
		var rnd = new System.Random(1000 + (int)t * 37 + (int)f * 911);
		for (var y = 0; y < 16; y++)
			for (var x = 0; x < 16; x++)
				tex.SetPixel(x, y, Pixel(t, f, x, y, rnd));
		tex.Apply();
		var m = new Material(lit) { name = tex.name, mainTexture = tex };
		m.SetFloat("_Glossiness", 0.15f);
		m.SetFloat("_Metallic", 0f);
		return m;
	}

	private static Color Vary(Color baseC, System.Random rnd, int amt)
	{
		var d = (rnd.Next(-amt, amt + 1)) / 255f;
		return new Color(
			Mathf.Clamp01(baseC.r + d), Mathf.Clamp01(baseC.g + d), Mathf.Clamp01(baseC.b + d), 1f);
	}

	private static Color C(int r, int g, int b) => new(r / 255f, g / 255f, b / 255f);

	private static Color Pixel(BlockType t, Face f, int x, int y, System.Random rnd)
	{
		switch (t)
		{
			case BlockType.Grass:
				if (f == Face.Top) return Vary(C(106, 176, 64), rnd, 14);
				if (f == Face.Bottom) return DirtPx(rnd);
				return y >= 12 - ((x * 7) % 3) ? Vary(C(106, 176, 64), rnd, 10) : DirtPx(rnd);
			case BlockType.Dirt:
				return DirtPx(rnd);
			case BlockType.Stone:
			{
				var c = Vary(C(128, 128, 128), rnd, 9);
				if ((x == 3 && y > 4 && y < 9) || (y == 11 && x > 8 && x < 13)) c = C(96, 96, 96);
				return c;
			}
			case BlockType.Log:
				if (f == Face.Top || f == Face.Bottom)
				{
					var ring = Math.Max(Math.Abs(x - 7.5f), Math.Abs(y - 7.5f));
					return ((int)ring % 2 == 0) ? C(177, 142, 90) : C(135, 106, 62);
				}
				return (x % 4 == 0) ? Vary(C(84, 66, 38), rnd, 8) : Vary(C(106, 85, 50), rnd, 10);
			case BlockType.Planks:
			{
				var c = Vary(C(176, 144, 88), rnd, 8);
				if (y % 4 == 3) c = C(122, 96, 54);
				if ((y % 4 != 3) && ((x + (y / 4) * 5) % 8 == 7)) c = C(122, 96, 54);
				return c;
			}
			case BlockType.Leaves:
			{
				var r = rnd.Next(100);
				if (r < 14) return C(28, 62, 18);
				if (r < 24) return C(84, 148, 56);
				return Vary(C(56, 118, 38), rnd, 12);
			}
			default:
				return Color.magenta;
		}
	}

	private static Color DirtPx(System.Random rnd)
	{
		var r = rnd.Next(100);
		if (r < 10) return C(106, 72, 44);
		if (r < 18) return C(160, 122, 88);
		return Vary(C(134, 96, 67), rnd, 10);
	}

	/// <summary>Unit cube centred on the origin. Submesh 0: sides, 1: top, 2: bottom.</summary>
	private static Mesh BuildMesh()
	{
		var verts = new System.Collections.Generic.List<Vector3>();
		var norms = new System.Collections.Generic.List<Vector3>();
		var uvs = new System.Collections.Generic.List<Vector2>();
		var sides = new System.Collections.Generic.List<int>();
		var top = new System.Collections.Generic.List<int>();
		var bottom = new System.Collections.Generic.List<int>();

		void Quad(Vector3 a, Vector3 b, Vector3 c, Vector3 d, Vector3 n, System.Collections.Generic.List<int> tris)
		{
			var i = verts.Count;
			verts.Add(a); verts.Add(b); verts.Add(c); verts.Add(d);
			for (var k = 0; k < 4; k++) { norms.Add(n); }
			uvs.Add(new Vector2(0, 0)); uvs.Add(new Vector2(1, 0)); uvs.Add(new Vector2(1, 1)); uvs.Add(new Vector2(0, 1));
			tris.Add(i); tris.Add(i + 2); tris.Add(i + 1);
			tris.Add(i); tris.Add(i + 3); tris.Add(i + 2);
		}

		const float h = 0.5f;
		// +Z front, -Z back, +X right, -X left (outward faces, CCW seen from outside)
		Quad(new Vector3(-h, -h, h), new Vector3(h, -h, h), new Vector3(h, h, h), new Vector3(-h, h, h), Vector3.forward, sides);
		Quad(new Vector3(h, -h, -h), new Vector3(-h, -h, -h), new Vector3(-h, h, -h), new Vector3(h, h, -h), Vector3.back, sides);
		Quad(new Vector3(h, -h, h), new Vector3(h, -h, -h), new Vector3(h, h, -h), new Vector3(h, h, h), Vector3.right, sides);
		Quad(new Vector3(-h, -h, -h), new Vector3(-h, -h, h), new Vector3(-h, h, h), new Vector3(-h, h, -h), Vector3.left, sides);
		Quad(new Vector3(-h, h, h), new Vector3(h, h, h), new Vector3(h, h, -h), new Vector3(-h, h, -h), Vector3.up, top);
		Quad(new Vector3(-h, -h, -h), new Vector3(h, -h, -h), new Vector3(h, -h, h), new Vector3(-h, -h, h), Vector3.down, bottom);

		var mesh = new Mesh { name = "blockcraft_cube" };
		mesh.SetVertices(verts);
		mesh.SetNormals(norms);
		mesh.SetUVs(0, uvs);
		mesh.subMeshCount = 3;
		mesh.SetTriangles(sides, 0);
		mesh.SetTriangles(top, 1);
		mesh.SetTriangles(bottom, 2);
		mesh.RecalculateBounds();
		return mesh;
	}
}
