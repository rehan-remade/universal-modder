using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;

namespace BlockCraft;

/// <summary>Marks a placed block: which parent it rides and which grid cell it owns there.</summary>
public class PlacedBlock : MonoBehaviour
{
	public Transform ParentKey;
	public Vector3Int Cell;
	public BlockType Type;
}

/// <summary>
/// The block tool. Like the portal gun it lives outside the game's ToolModeSwapper: the equip key
/// stows whatever the swapper holds, and taking out a game tool puts this one away.
/// Blocks are parented to the body they were placed against (portal gun's PickParent pattern), so
/// they ride planets, islands and the ship, and they live on a grid in that parent's local space.
/// </summary>
public class BlockTool : MonoBehaviour
{
	public static BlockTool Instance;

	public bool Equipped { get; private set; }
	public BlockType Selected = BlockType.Grass;

	private OWCamera _cam;
	private ToolModeSwapper _swapper;
	private Key _equipKey = Key.Digit6;
	private float _equipTime;
	private bool _waitSwapper;

	private GameObject _held;        // cube in the player's hand (camera child, no collider)
	private MeshRenderer _heldRenderer;
	private GameObject _ghost;       // placement preview (scene root, no collider)
	private MeshRenderer _ghostRenderer;
	private GameObject _crack;       // break progress overlay
	private BlockHud _hud;

	private readonly Dictionary<Transform, Dictionary<Vector3Int, PlacedBlock>> _placed = new();
	private int _placedCount;

	private Transform _targetParent;
	private Vector3Int _targetCell;
	private PlacedBlock _targetBlock;
	private bool _hasTarget;
	private float _breakProgress;
	private PlacedBlock _breakTarget;
	private float _nextPlace;

	private class Poof { public GameObject Go; public float T; public Vector3 Scale; }
	private readonly List<Poof> _poofs = new();

	private float Size => BlockCraftMod.Instance != null ? BlockCraftMod.Instance.BlockSize : 1f;
	private float Reach => Mathf.Max(5f, 6f * Size);

	public static BlockTool Create()
	{
		var go = new GameObject("BlockTool");
		var t = go.AddComponent<BlockTool>();
		Instance = t;
		return t;
	}

	private void Start()
	{
		_cam = Locator.GetPlayerCamera();
		_swapper = Locator.GetToolModeSwapper();
		_equipKey = ParseKey(BlockCraftMod.Instance.EquipKey);
		_hud = gameObject.AddComponent<BlockHud>();
		_hud.Tool = this;

		_held = MakeCube("HeldBlock", null);
		_held.transform.SetParent(_cam.transform, false);
		_held.transform.localPosition = new Vector3(0.44f, -0.42f, 0.78f);
		_held.transform.localRotation = Quaternion.Euler(14f, -22f, 6f);
		_held.transform.localScale = Vector3.one * 0.27f;
		var vmLayer = LayerMask.NameToLayer("VisibleToPlayer");
		if (vmLayer >= 0) SetLayerRecursive(_held, vmLayer);
		_heldRenderer = _held.GetComponent<MeshRenderer>();
		_held.SetActive(false);

		_ghost = MakeCube("BlockGhost", null);
		_ghostRenderer = _ghost.GetComponent<MeshRenderer>();
		_ghost.layer = 2; // Ignore Raycast
		_ghost.SetActive(false);

		_crack = MakeCube("BlockCrack", null);
		_crack.GetComponent<MeshRenderer>().sharedMaterial = BlockTextures.Crack;
		_crack.layer = 2;
		_crack.SetActive(false);

		RefreshHeld();
		BlockCraftMod.Log($"block tool ready: equip key {_equipKey}, block size {Size:F2} m");
	}

	private void OnDestroy()
	{
		if (Instance == this) Instance = null;
	}

	private static GameObject MakeCube(string name, Transform parent)
	{
		var go = new GameObject(name);
		if (parent != null) go.transform.SetParent(parent, false);
		go.AddComponent<MeshFilter>().sharedMesh = BlockTextures.BlockMesh;
		go.AddComponent<MeshRenderer>();
		return go;
	}

	private static void SetLayerRecursive(GameObject go, int layer)
	{
		go.layer = layer;
		foreach (Transform child in go.transform) SetLayerRecursive(child.gameObject, layer);
	}

	private static Key ParseKey(string s)
	{
		if (string.IsNullOrEmpty(s)) return Key.Digit6;
		if (s.Length == 1 && char.IsDigit(s[0])) return s[0] == '0' ? Key.Digit0 : Key.Digit1 + (s[0] - '1');
		return System.Enum.TryParse<Key>(s, true, out var k) ? k : Key.Digit6;
	}

	private static bool HandsBusy() =>
		PlayerState.InDreamWorld() || PlayerState.IsAttached() || PlayerState.InConversation() || PlayerState.IsDead();

	private static bool CanUse() => OWInput.IsInputMode(InputMode.Character) && !HandsBusy();

	// --- equip ------------------------------------------------------------------------------------

	public void Toggle() { if (Equipped) Holster(); else Equip(); }

	public void Equip()
	{
		if (Equipped || !CanUse()) return;
		var item = _swapper.GetItemCarryTool();
		if (item != null && item.GetHeldItem() != null)
		{
			_hud.Show("Drop what you're carrying to use the block tool");
			return;
		}
		_waitSwapper = _swapper.GetToolMode() != ToolMode.None;
		if (_waitSwapper) _swapper.UnequipTool();
		Equipped = true;
		_equipTime = Time.time;
		_held.SetActive(true);
		Locator.GetPlayerAudioController()?.PlayEquipTool();
		_hud.Show($"Block tool: {BlockTextures.Names[(int)Selected]} (scroll to change, right click place, hold left click break)");
	}

	public void Holster()
	{
		if (!Equipped) return;
		Equipped = false;
		_held.SetActive(false);
		_ghost.SetActive(false);
		_crack.SetActive(false);
		_breakTarget = null;
		_breakProgress = 0f;
		Locator.GetPlayerAudioController()?.PlayUnequipTool();
	}

	/// <summary>From the ToolModeSwapper.Update Harmony prefix: the game must not see its tool buttons.</summary>
	public void ConsumeGameToolInput()
	{
		if (!Equipped) return;
		InputLibrary.toolActionPrimary.ConsumeInput();
		InputLibrary.toolActionSecondary.ConsumeInput();
	}

	// --- update -----------------------------------------------------------------------------------

	private void Update()
	{
		var kb = Keyboard.current;
		if (kb != null && kb[_equipKey].wasPressedThisFrame && OWInput.IsInputMode(InputMode.Character))
			Toggle();

		UpdatePoofs();

		if (!Equipped) return;

		var mode = _swapper.GetToolMode();
		if (_waitSwapper && mode == ToolMode.None) _waitSwapper = false;
		if (((mode != ToolMode.None && !_waitSwapper) || HandsBusy()) && Time.time > _equipTime + 0.25f)
		{
			Holster();
			return;
		}
		if (!OWInput.IsInputMode(InputMode.Character)) { _ghost.SetActive(false); return; }

		var scroll = Mouse.current != null ? Mouse.current.scroll.ReadValue().y : 0f;
		if (scroll != 0f) Cycle(scroll > 0 ? 1 : -1);

		UpdateTargeting();
		ReadUseInput();
	}

	private void Cycle(int dir)
	{
		var n = BlockTextures.Names.Length;
		Selected = (BlockType)(((int)Selected + dir + n) % n);
		RefreshHeld();
		_hud.Show(BlockTextures.Names[(int)Selected]);
	}

	private void RefreshHeld()
	{
		if (_heldRenderer != null)
			_heldRenderer.sharedMaterials = BlockTextures.SubmeshMaterialsFor(Selected);
	}

	// --- targeting --------------------------------------------------------------------------------

	private void UpdateTargeting()
	{
		_hasTarget = false;
		_targetBlock = null;
		_targetParent = null;

		var origin = _cam.transform.position;
		var dir = _cam.transform.forward;
		if (!Physics.Raycast(origin, dir, out var hit, Reach, OWLayerMask.physicalMask, QueryTriggerInteraction.Ignore)
			|| hit.collider == null)
		{
			_ghost.SetActive(false);
			return;
		}

		var s = Size;
		_lastHitLayer = hit.collider.gameObject.layer;
		var marker = hit.collider.GetComponentInParent<PlacedBlock>();
		if (marker != null)
		{
			_targetBlock = marker;
			_targetParent = marker.ParentKey;
			var axis = DominantAxis(_targetParent.InverseTransformDirection(hit.normal));
			_targetCell = marker.Cell + axis;
		}
		else
		{
			_targetParent = PickParent(hit.collider, out _);
			if (_targetParent == null) { _ghost.SetActive(false); return; }
			var localPoint = _targetParent.InverseTransformPoint(hit.point);
			var localNormal = DominantAxis(_targetParent.InverseTransformDirection(hit.normal));
			var probe = localPoint + (Vector3)localNormal * (s * 0.5f - 0.02f);
			_targetCell = CellOf(probe, s);
		}
		_hasTarget = true;

		// Preview the cell the next block would occupy.
		var occupied = IsOccupied(_targetParent, _targetCell);
		var world = _targetParent.TransformPoint((Vector3)_targetCell * s);
		_ghost.SetActive(true);
		_ghost.transform.SetPositionAndRotation(world, _targetParent.rotation);
		var gs = s * 1.002f;
		_ghost.transform.localScale = new Vector3(gs, gs, gs);
		var tooClose = Vector3.Distance(world, Locator.GetPlayerTransform().position) < s * 1.05f;
		var gm = (occupied || tooClose) ? BlockTextures.GhostBad : BlockTextures.GhostOk;
		_ghostRenderer.sharedMaterials = new[] { gm, gm, gm };
	}

	private static Vector3Int DominantAxis(Vector3 v)
	{
		var ax = Mathf.Abs(v.x); var ay = Mathf.Abs(v.y); var az = Mathf.Abs(v.z);
		if (ax >= ay && ax >= az) return new Vector3Int(v.x >= 0 ? 1 : -1, 0, 0);
		if (ay >= ax && ay >= az) return new Vector3Int(0, v.y >= 0 ? 1 : -1, 0);
		return new Vector3Int(0, 0, v.z >= 0 ? 1 : -1);
	}

	private static Vector3Int CellOf(Vector3 localPoint, float s) =>
		new(Mathf.RoundToInt(localPoint.x / s), Mathf.RoundToInt(localPoint.y / s), Mathf.RoundToInt(localPoint.z / s));

	private bool IsOccupied(Transform parent, Vector3Int cell) =>
		_placed.TryGetValue(parent, out var map) && map.ContainsKey(cell);

	/// <summary>Collider transform when it isn't skewed, else its rigidbody (portal gun pattern).</summary>
	private static Transform PickParent(Collider wall, out OWRigidbody body)
	{
		body = wall != null ? wall.GetAttachedOWRigidbody() : null;
		if (wall == null) return null;
		var sc = wall.transform.lossyScale;
		var uniform = Mathf.Abs(sc.x - sc.y) < 1e-3f * Mathf.Abs(sc.x) && Mathf.Abs(sc.x - sc.z) < 1e-3f * Mathf.Abs(sc.x);
		if (uniform) return wall.transform;
		return body != null ? body.transform : wall.transform.root;
	}

	// --- use --------------------------------------------------------------------------------------

	private void ReadUseInput()
	{
		var mouse = Mouse.current;
		if (mouse == null) return;

		// Place: right mouse, repeat while held.
		if ((mouse.rightButton.wasPressedThisFrame || (mouse.rightButton.isPressed && Time.time >= _nextPlace)) && _hasTarget)
		{
			_nextPlace = Time.time + 0.18f;
			TryPlace();
		}

		// Break: hold left mouse on a placed block.
		if (mouse.leftButton.isPressed && _targetBlock != null)
		{
			if (_breakTarget != _targetBlock) { _breakTarget = _targetBlock; _breakProgress = 0f; }
			_breakProgress += Time.deltaTime / 0.4f;
			ShowCrack(_breakTarget, _breakProgress);
			if (_breakProgress >= 1f)
			{
				BreakBlock(_breakTarget);
				_breakTarget = null;
				_breakProgress = 0f;
				_crack.SetActive(false);
			}
		}
		else
		{
			_breakTarget = null;
			_breakProgress = 0f;
			_crack.SetActive(false);
		}
	}

	private void ShowCrack(PlacedBlock b, float progress)
	{
		_crack.SetActive(true);
		_crack.transform.SetPositionAndRotation(b.transform.position, b.transform.rotation);
		_crack.transform.localScale = b.transform.lossyScale * 1.01f;
		var cm = BlockTextures.Crack;
		_crack.GetComponent<MeshRenderer>().sharedMaterials = new[] { cm, cm, cm };
	}

	private void TryPlace()
	{
		if (_targetParent == null) return;
		var s = Size;
		if (IsOccupied(_targetParent, _targetCell)) return;
		var max = BlockCraftMod.Instance != null ? BlockCraftMod.Instance.MaxBlocks : 1000;
		if (_placedCount >= max) { _hud.Show($"Block limit reached ({max}). Break some first"); return; }
		var world = _targetParent.TransformPoint((Vector3)_targetCell * s);
		if (Vector3.Distance(world, Locator.GetPlayerTransform().position) < s * 1.05f)
		{
			_hud.Show("Too close to yourself");
			return;
		}

		var go = MakeCube("Block_" + Selected, null);
		go.transform.SetPositionAndRotation(world, _targetParent.rotation);
		go.transform.SetParent(_targetParent, true);
		FixScale(go.transform, s);
		var col = go.AddComponent<BoxCollider>();
		col.size = Vector3.one;
		// Live on the same layer as the surface that was hit, so raycasts and the
		// character controller treat blocks like terrain.
		go.layer = _lastHitLayer;
		var rend = go.GetComponent<MeshRenderer>();
		rend.sharedMaterials = BlockTextures.SubmeshMaterialsFor(Selected);
		var marker = go.AddComponent<PlacedBlock>();
		marker.ParentKey = _targetParent;
		marker.Cell = _targetCell;
		marker.Type = Selected;

		if (!_placed.TryGetValue(_targetParent, out var map))
		{
			map = new Dictionary<Vector3Int, PlacedBlock>();
			_placed[_targetParent] = map;
		}
		map[_targetCell] = marker;
		_placedCount++;
	}

	private int _lastHitLayer;

	private void BreakBlock(PlacedBlock b)
	{
		if (b == null) return;
		if (_placed.TryGetValue(b.ParentKey, out var map)) map.Remove(b.Cell);
		_placedCount = Mathf.Max(0, _placedCount - 1);
		SpawnPoof(b);
		Destroy(b.gameObject);
	}

	private void SpawnPoof(PlacedBlock b)
	{
		var go = MakeCube("BlockPoof", null);
		go.transform.SetPositionAndRotation(b.transform.position, b.transform.rotation);
		go.transform.localScale = b.transform.lossyScale;
		go.GetComponent<MeshRenderer>().sharedMaterials = BlockTextures.SubmeshMaterialsFor(b.Type);
		go.layer = 2;
		_poofs.Add(new Poof { Go = go, T = 0f, Scale = go.transform.localScale });
	}

	private void UpdatePoofs()
	{
		for (var i = _poofs.Count - 1; i >= 0; i--)
		{
			var p = _poofs[i];
			p.T += Time.deltaTime / 0.16f;
			if (p.Go == null || p.T >= 1f)
			{
				if (p.Go != null) Destroy(p.Go);
				_poofs.RemoveAt(i);
				continue;
			}
			p.Go.transform.localScale = p.Scale * (1f - p.T);
		}
	}

	/// <summary>Counteracts the parent's world scale so the block is exactly Size in world units.</summary>
	private static void FixScale(Transform t, float worldSize)
	{
		var ls = t.lossyScale;
		var l = t.localScale;
		t.localScale = new Vector3(
			ls.x != 0 ? l.x / Mathf.Abs(ls.x) * worldSize : worldSize,
			ls.y != 0 ? l.y / Mathf.Abs(ls.y) * worldSize : worldSize,
			ls.z != 0 ? l.z / Mathf.Abs(ls.z) * worldSize : worldSize);
	}
}
