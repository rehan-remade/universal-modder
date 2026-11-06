using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

namespace OWPortalGun;

/// <summary>Everything tools/convert.py wrote, loaded once per game session.</summary>
public class GunAssets
{
	public class Bone
	{
		public string Name;
		public int Parent;
		public Vector3 Pos;
		public Quaternion Rot;
		public Matrix4x4 BindPose;
	}

	public class Submesh
	{
		public string Material;
		public int[] Indices;
	}

	public class Attachment
	{
		public string Name;
		public int Bone;
		public Vector3 Pos;
		public Quaternion Rot;
	}

	public class Sequence
	{
		public string Name;
		public string Activity;
		public bool Loop;
		public float Fps;
		public int Frames;
		public Vector3[] Pos; // [frame * bones + bone]
		public Quaternion[] Rot;
		public float Duration => Frames > 1 ? (Frames - 1) / Fps : 0f;
	}

	public readonly string Folder;
	public readonly List<Bone> Bones = new();
	public Vector3[] Vertices, Normals;
	public Vector2[] Uvs;
	public BoneWeight[] Weights;
	public readonly List<Submesh> Submeshes = new();
	public readonly List<Attachment> Attachments = new();
	public readonly Dictionary<string, Sequence> Sequences = new();
	public readonly Dictionary<string, Texture2D> Textures = new();
	public readonly Dictionary<string, AudioClip> Sounds = new();

	public GunAssets(string folder)
	{
		Folder = folder;
		LoadModel(Path.Combine(folder, "portalgun.owpg"));
		foreach (var png in Directory.GetFiles(Path.Combine(folder, "textures"), "*.png"))
		{
			var name = Path.GetFileNameWithoutExtension(png);
			var linear = name.EndsWith("_normal");
			var tex = new Texture2D(2, 2, TextureFormat.RGBA32, true, linear) { name = name };
			tex.LoadImage(File.ReadAllBytes(png));
			tex.wrapMode = name.Contains("color") ? TextureWrapMode.Clamp : TextureWrapMode.Repeat;
			tex.anisoLevel = 4;
			Textures[name] = tex;
		}
		foreach (var wav in Directory.GetFiles(Path.Combine(folder, "sounds"), "*.wav"))
		{
			var clip = LoadWav(wav);
			if (clip != null)
				Sounds[clip.name] = clip;
		}
	}

	private void LoadModel(string path)
	{
		using var r = new BinaryReader(File.OpenRead(path));
		if (Encoding.ASCII.GetString(r.ReadBytes(4)) != "OWPG")
			throw new InvalidDataException(path + " is not an OWPG file");
		var version = r.ReadInt32();
		if (version != 1)
			throw new InvalidDataException("unsupported OWPG version " + version);

		var nb = r.ReadInt32();
		for (var i = 0; i < nb; i++)
		{
			var b = new Bone { Name = Str(r), Parent = r.ReadInt32(), Pos = V3(r), Rot = Q(r) };
			var m = new Matrix4x4();
			for (var row = 0; row < 4; row++)
				for (var col = 0; col < 4; col++)
					m[row, col] = r.ReadSingle();
			b.BindPose = m;
			Bones.Add(b);
		}

		var nv = r.ReadInt32();
		Vertices = new Vector3[nv];
		Normals = new Vector3[nv];
		Uvs = new Vector2[nv];
		Weights = new BoneWeight[nv];
		for (var i = 0; i < nv; i++) Vertices[i] = V3(r);
		for (var i = 0; i < nv; i++) Normals[i] = V3(r);
		for (var i = 0; i < nv; i++) Uvs[i] = new Vector2(r.ReadSingle(), r.ReadSingle());
		var bi = new int[nv * 4];
		for (var i = 0; i < bi.Length; i++) bi[i] = r.ReadInt32();
		for (var i = 0; i < nv; i++)
		{
			Weights[i] = new BoneWeight
			{
				boneIndex0 = bi[i * 4], boneIndex1 = bi[i * 4 + 1], boneIndex2 = bi[i * 4 + 2], boneIndex3 = bi[i * 4 + 3],
				weight0 = r.ReadSingle(), weight1 = r.ReadSingle(), weight2 = r.ReadSingle(), weight3 = r.ReadSingle()
			};
		}

		var ns = r.ReadInt32();
		for (var i = 0; i < ns; i++)
		{
			var s = new Submesh { Material = Str(r) };
			s.Indices = new int[r.ReadInt32()];
			for (var k = 0; k < s.Indices.Length; k++) s.Indices[k] = r.ReadInt32();
			Submeshes.Add(s);
		}

		var na = r.ReadInt32();
		for (var i = 0; i < na; i++)
			Attachments.Add(new Attachment { Name = Str(r), Bone = r.ReadInt32(), Pos = V3(r), Rot = Q(r) });

		var nq = r.ReadInt32();
		for (var i = 0; i < nq; i++)
		{
			var s = new Sequence { Name = Str(r), Activity = Str(r), Loop = r.ReadInt32() != 0, Fps = r.ReadSingle(), Frames = r.ReadInt32() };
			s.Pos = new Vector3[s.Frames * nb];
			s.Rot = new Quaternion[s.Frames * nb];
			for (var k = 0; k < s.Pos.Length; k++)
			{
				s.Pos[k] = V3(r);
				s.Rot[k] = Q(r);
			}
			Sequences[s.Name] = s;
		}
	}

	private static string Str(BinaryReader r) => Encoding.UTF8.GetString(r.ReadBytes(r.ReadInt32()));
	private static Vector3 V3(BinaryReader r) => new(r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
	private static Quaternion Q(BinaryReader r) => new(r.ReadSingle(), r.ReadSingle(), r.ReadSingle(), r.ReadSingle());

	/// <summary>PCM16 RIFF/WAVE to AudioClip (Portal 2's weapon sounds are all PCM16).</summary>
	private static AudioClip LoadWav(string path)
	{
		var d = File.ReadAllBytes(path);
		int channels = 0, rate = 0, bits = 0, dataOff = -1, dataLen = 0;
		var p = 12;
		while (p + 8 <= d.Length)
		{
			var id = Encoding.ASCII.GetString(d, p, 4);
			var n = BitConverter.ToInt32(d, p + 4);
			if (id == "fmt ")
			{
				if (BitConverter.ToInt16(d, p + 8) != 1)
					return null;
				channels = BitConverter.ToInt16(d, p + 10);
				rate = BitConverter.ToInt32(d, p + 12);
				bits = BitConverter.ToInt16(d, p + 22);
			}
			else if (id == "data")
			{
				dataOff = p + 8;
				dataLen = Math.Min(n, d.Length - dataOff);
			}
			p += 8 + n + (n & 1);
		}
		if (dataOff < 0 || bits != 16 || channels == 0)
			return null;
		var samples = dataLen / 2;
		var f = new float[samples];
		for (var i = 0; i < samples; i++)
			f[i] = BitConverter.ToInt16(d, dataOff + i * 2) / 32768f;
		var clip = AudioClip.Create(Path.GetFileNameWithoutExtension(path), samples / channels, channels, rate, false);
		clip.SetData(f, 0);
		return clip;
	}
}
