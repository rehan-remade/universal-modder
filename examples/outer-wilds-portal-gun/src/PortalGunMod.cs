using System;
using System.IO;
using System.Reflection;
using HarmonyLib;
using OWML.Common;
using OWML.ModHelper;
using UnityEngine;

namespace OWPortalGun;

public class PortalGunMod : ModBehaviour
{
	public static PortalGunMod Instance;

	public GunAssets Assets;
	public string EquipKey = "5";
	public float Volume = 0.7f;
	public string ModFolder;

	private void Awake()
	{
		Instance = this;
	}

	private void Start()
	{
		ModFolder = ModHelper.Manifest.ModFolderPath;
		Configure(ModHelper.Config);
		new Harmony("charlystereo.PortalGun").PatchAll(Assembly.GetExecutingAssembly());
		Materials.Init();
		LoadAssets();
		gameObject.AddComponent<DevBridge>();
		LoadManager.OnCompleteSceneLoad += OnCompleteSceneLoad;
		if (LoadManager.GetCurrentScene() == OWScene.SolarSystem)
			OnCompleteSceneLoad(OWScene.TitleScreen, OWScene.SolarSystem);
		Log("Portal Gun loaded", MessageType.Success);
	}

	public override void Configure(IModConfig config)
	{
		EquipKey = config.GetSettingsValue<string>("equipKey");
		Volume = config.GetSettingsValue<float>("volume");
		var folder = config.GetSettingsValue<string>("assetFolder");
		if (Assets != null && !string.IsNullOrEmpty(folder) && folder != Assets.Folder)
			LoadAssets();
	}

	private string AssetFolder()
	{
		var folder = ModHelper.Config.GetSettingsValue<string>("assetFolder");
		if (string.IsNullOrEmpty(folder))
			folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OWPortalGun");
		return folder;
	}

	private void LoadAssets()
	{
		var folder = AssetFolder();
		try
		{
			var t = Time.realtimeSinceStartup;
			Assets = new GunAssets(folder);
			Log($"assets from {folder}: {Assets.Vertices.Length} verts, {Assets.Bones.Count} bones, {Assets.Sequences.Count} sequences, " +
				$"{Assets.Textures.Count} textures, {Assets.Sounds.Count} sounds in {(Time.realtimeSinceStartup - t) * 1000f:F0} ms");
		}
		catch (Exception e)
		{
			Assets = null;
			Log($"No converted portal gun in {folder}. Run tools/convert.py (it reads your Portal 2 install). {e.Message}", MessageType.Error);
		}
	}

	private void OnCompleteSceneLoad(OWScene previous, OWScene scene)
	{
		if (scene != OWScene.SolarSystem || Assets == null)
			return;
		// Wait one frame so Locator has the player, camera and tool swapper.
		ModHelper.Events.Unity.FireOnNextUpdate(() =>
		{
			var system = PortalSystem.Create(Assets);
			PortalGun.Create(Assets, system);
			Log("portal gun added to the loop");
		});
	}

	public static void Log(string msg, MessageType type = MessageType.Message)
	{
		if (Instance != null && Instance.ModHelper != null)
			Instance.ModHelper.Console.WriteLine(msg, type);
		else
			Debug.Log("[PortalGun] " + msg);
		DevBridge.Append(msg);
	}
}

[HarmonyPatch(typeof(ToolModeSwapper), "Update")]
internal static class ToolModeSwapperUpdatePatch
{
	// Runs before the swapper reads the tool buttons, so right mouse doesn't also take out the scout launcher.
	private static void Prefix() => PortalGun.Instance?.ConsumeGameToolInput();
}

[HarmonyPatch(typeof(ReferenceFrameTracker), "UpdateTargeting")]
internal static class LockOnPatch
{
	// Left mouse is lock-on; with the gun out it fires the blue portal instead.
	private static void Prefix()
	{
		if (PortalGun.Instance != null && PortalGun.Instance.Equipped && OWInput.IsInputMode(InputMode.Character))
			InputLibrary.lockOn.ConsumeInput();
	}
}

[HarmonyPatch(typeof(PlayerCharacterController), "IsValidGroundedHit")]
internal static class GroundedHitPatch
{
	// The controller finds the floor with a sphere cast, which IgnoreCollision doesn't affect:
	// without this the player hovers over a floor portal instead of dropping in.
	private static void Postfix(PlayerCharacterController __instance, RaycastHit hit, ref bool __result)
	{
		if (__result && PortalSystem.Instance != null && hit.collider != null
			&& PortalSystem.Instance.IsHoleHit(Locator.GetPlayerBody(), hit.collider, hit.point))
			__result = false;
	}
}

[HarmonyPatch(typeof(ProbeAnchor), nameof(ProbeAnchor.AnchorToObject))]
internal static class ProbeAnchorPatch
{
	// The scout would stick to the wall behind a portal; send it through instead.
	private static bool Prefix(Vector3 hitPoint)
	{
		var probe = Locator.GetProbe();
		if (PortalSystem.Instance == null || probe == null || !probe.IsLaunched())
			return true;
		return !PortalSystem.Instance.TryPassThrough(probe.GetOWRigidbody(), hitPoint);
	}
}
