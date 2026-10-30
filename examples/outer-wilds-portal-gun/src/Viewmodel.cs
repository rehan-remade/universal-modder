using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace OWPortalGun;

/// <summary>
/// The converted Portal 2 viewmodel: a SkinnedMeshRenderer whose bones are driven by the baked sequences.
/// The model's origin is the eye, so the whole thing sits at the camera. It is shrunk around the eye by
/// <see cref="DepthScale"/>: the picture stays the same but the gun never reaches walls in front of the player.
/// </summary>
public class Viewmodel : MonoBehaviour
{
	// With the game's viewmodel shaders the gun keeps its real size; without them it is shrunk towards
	// the eye (same picture, less depth) so it doesn't poke into walls.
	public static float DepthScale => Materials.GameViewmodel != null ? 1f : 0.3f;
	private const float CrossFade = 0.08f;

	private GunAssets _assets;
	private Transform[] _bones;
	private SkinnedMeshRenderer _renderer, _prepass;
	private Material _bodyMaterial;
	private readonly Dictionary<string, Transform> _attachments = new();

	private GunAssets.Sequence _seq;
	private string _then;
	private float _time;
	private float _fadeLeft;
	private Vector3[] _fadePos;
	private Quaternion[] _fadeRot;

	public bool Visible
	{
		get => _renderer.enabled;
		set
		{
			_renderer.enabled = value;
			if (_prepass != null) _prepass.enabled = value;
		}
	}

	public string CurrentSequence => _seq?.Name;
	public bool Finished => _seq != null && !_seq.Loop && _time >= _seq.Duration;

	public static Viewmodel Create(GunAssets assets, Transform camera, int layer)
	{
		var go = new GameObject("PortalGunViewmodel");
		go.layer = layer;
		go.transform.SetParent(camera, false);
		go.transform.localScale = Vector3.one * DepthScale;
		var vm = go.AddComponent<Viewmodel>();
		vm.Build(assets, layer);
		return vm;
	}

	private void Build(GunAssets assets, int layer)
	{
		_assets = assets;
		_bones = new Transform[assets.Bones.Count];
		for (var i = 0; i < _bones.Length; i++)
		{
			var b = assets.Bones[i];
			_bones[i] = new GameObject(b.Name) { layer = layer }.transform;
		}
		for (var i = 0; i < _bones.Length; i++)
		{
			var b = assets.Bones[i];
			_bones[i].SetParent(b.Parent >= 0 ? _bones[b.Parent] : transform, false);
			_bones[i].localPosition = b.Pos;
			_bones[i].localRotation = b.Rot;
		}
		foreach (var a in assets.Attachments)
		{
			var t = new GameObject("att_" + a.Name).transform;
			t.SetParent(_bones[a.Bone], false);
			t.localPosition = a.Pos;
			t.localRotation = a.Rot;
			_attachments[a.Name] = t;
		}

		var mesh = new Mesh { name = "v_portalgun", indexFormat = IndexFormat.UInt32 };
		mesh.vertices = assets.Vertices;
		mesh.normals = assets.Normals;
		mesh.uv = assets.Uvs;
		mesh.boneWeights = assets.Weights;
		var bind = new Matrix4x4[assets.Bones.Count];
		for (var i = 0; i < bind.Length; i++) bind[i] = assets.Bones[i].BindPose;
		mesh.bindposes = bind;
		mesh.subMeshCount = assets.Submeshes.Count;
		var mats = new Material[assets.Submeshes.Count];
		for (var i = 0; i < assets.Submeshes.Count; i++)
		{
			mesh.SetTriangles(assets.Submeshes[i].Indices, i);
			mats[i] = Materials.ForGun(assets, assets.Submeshes[i].Material);
			if (assets.Submeshes[i].Material == "v_portalgun")
				_bodyMaterial = mats[i];
		}
		mesh.RecalculateTangents();
		mesh.RecalculateBounds();

		var meshGo = new GameObject("mesh") { layer = layer };
		meshGo.transform.SetParent(transform, false);
		_renderer = meshGo.AddComponent<SkinnedMeshRenderer>();
		_renderer.sharedMesh = mesh;
		_renderer.bones = _bones;
		_renderer.rootBone = transform;
		_renderer.sharedMaterials = mats;
		_renderer.updateWhenOffscreen = true;
		_renderer.shadowCastingMode = ShadowCastingMode.Off;
		_renderer.receiveShadows = false;

		// The game's tools draw a depth prepass first; do the same with a second renderer on the same bones.
		if (Materials.GameViewmodelPrepass != null)
		{
			var preGo = new GameObject("prepass") { layer = layer };
			preGo.transform.SetParent(transform, false);
			var pre = preGo.AddComponent<SkinnedMeshRenderer>();
			pre.sharedMesh = mesh;
			pre.bones = _bones;
			pre.rootBone = transform;
			var pm = new Material[mats.Length];
			for (var i = 0; i < pm.Length; i++) pm[i] = Materials.GameViewmodelPrepass;
			pre.sharedMaterials = pm;
			pre.updateWhenOffscreen = true;
			pre.shadowCastingMode = ShadowCastingMode.Off;
			pre.receiveShadows = false;
			_prepass = pre;
		}

		_fadePos = new Vector3[_bones.Length];
		_fadeRot = new Quaternion[_bones.Length];
	}

	/// <summary>0 = neutral (no portal fired yet), 1 = blue, 2 = orange; Portal 2's three skins.</summary>
	public void SetSkin(int skin)
	{
		var name = skin == 1 ? "v_portalgun_blue" : skin == 2 ? "v_portalgun_orange" : "v_portalgun";
		if (_assets.Textures.TryGetValue(name, out var tex))
			_bodyMaterial.mainTexture = tex;
	}

	public Transform Attachment(string name) => _attachments.TryGetValue(name, out var t) ? t : transform;

	public void Play(string name, string then = "idle")
	{
		if (!_assets.Sequences.TryGetValue(name, out var seq))
			return;
		if (_seq != null)
		{
			for (var i = 0; i < _bones.Length; i++)
			{
				_fadePos[i] = _bones[i].localPosition;
				_fadeRot[i] = _bones[i].localRotation;
			}
			_fadeLeft = CrossFade;
		}
		_seq = seq;
		_then = then;
		_time = 0f;
		Apply();
	}

	private void LateUpdate()
	{
		if (_seq == null)
			return;
		_time += Time.deltaTime;
		if (!_seq.Loop && _time >= _seq.Duration && _then != null && _assets.Sequences.ContainsKey(_then))
			Play(_then, _then);
		_fadeLeft -= Time.deltaTime;
		Apply();
	}

	private void Apply()
	{
		var nb = _bones.Length;
		float f;
		if (_seq.Loop && _seq.Duration > 0)
			f = (_time % _seq.Duration) * _seq.Fps;
		else
			f = Mathf.Min(_time * _seq.Fps, _seq.Frames - 1);
		var i0 = Mathf.Clamp((int)f, 0, _seq.Frames - 1);
		var i1 = Mathf.Min(i0 + 1, _seq.Frames - 1);
		var t = f - i0;
		var fade = _fadeLeft > 0 ? 1f - _fadeLeft / CrossFade : 1f;
		for (var b = 0; b < nb; b++)
		{
			var p = Vector3.Lerp(_seq.Pos[i0 * nb + b], _seq.Pos[i1 * nb + b], t);
			var q = Quaternion.Slerp(_seq.Rot[i0 * nb + b], _seq.Rot[i1 * nb + b], t);
			if (fade < 1f)
			{
				p = Vector3.Lerp(_fadePos[b], p, fade);
				q = Quaternion.Slerp(_fadeRot[b], q, fade);
			}
			_bones[b].localPosition = p;
			_bones[b].localRotation = q;
		}
	}
}
