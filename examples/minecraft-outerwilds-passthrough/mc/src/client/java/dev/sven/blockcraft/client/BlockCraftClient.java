package dev.sven.blockcraft.client;

import dev.sven.blockcraft.BlockCraft;
import dev.sven.blockcraft.WorldBridge;
import java.util.List;
import java.util.Optional;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import net.minecraft.client.CloudStatus;
import net.minecraft.client.InactivityFpsLimit;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Options;
import net.minecraft.client.gui.screens.DeathScreen;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.client.tutorial.TutorialSteps;
import net.minecraft.core.HolderLookup;
import net.minecraft.core.HolderSet;
import net.minecraft.core.registries.Registries;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.LevelSettings;
import net.minecraft.world.level.WorldDataConfiguration;
import net.minecraft.world.level.biome.Biomes;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.levelgen.FlatLevelSource;
import net.minecraft.world.level.levelgen.WorldDimensions;
import net.minecraft.world.level.levelgen.WorldOptions;
import net.minecraft.world.level.levelgen.flat.FlatLayerInfo;
import net.minecraft.world.level.levelgen.flat.FlatLevelGeneratorSettings;
import net.minecraft.world.level.levelgen.presets.WorldPresets;

/**
 * The client half: opens the passthrough world, keeps the picture clean for compositing, and connects to
 * the host.
 *
 * <p>The world is a flat void: nothing but what the player builds. Per docs/CONTRACT.md the host's ground
 * arrives as barrier blocks, so the guest starts with no terrain of its own and matches what Outer Wilds
 * has underfoot.
 */
public class BlockCraftClient implements ClientModInitializer {
	/** The world the host plays in: an empty (void) creative world, so only what the player builds is Minecraft. */
	private static final String WORLD = "blockcraft";
	/** Run on the server once the player has joined. */
	private static final List<String> SETUP = List.of(
		"gamerule advance_time false",
		"gamerule advance_weather false",
		"gamerule spawn_mobs false",
		"gamerule spawn_monsters false",
		"gamerule spawn_patrols false",
		"gamerule spawn_phantoms false",
		"gamerule spawn_wandering_traders false",
		"gamerule send_command_feedback false",
		"gamerule log_admin_commands false",
		"gamerule keep_inventory true",
		"gamerule show_advancement_messages false",
		"difficulty normal",
		"time set noon",
		"weather clear",
		"item replace entity @a hotbar.0 with minecraft:grass_block 64",
		"item replace entity @a hotbar.1 with minecraft:oak_planks 64",
		"item replace entity @a hotbar.2 with minecraft:torch 64",
		"item replace entity @a hotbar.3 with minecraft:crafting_table",
		"item replace entity @a hotbar.4 with minecraft:stone 64",
		"item replace entity @a hotbar.5 with minecraft:glass 64",
		"item replace entity @a hotbar.6 with minecraft:oak_log 64",
		"item replace entity @a hotbar.7 with minecraft:diamond_pickaxe"
	);
	private static boolean configured;
	private static boolean worldRequested;
	/** Server ticks until the setup commands run (the player isn't in the player list yet when JOIN fires). */
	private static int setupIn = -1;
	private static int respawnIn;

	@Override
	public void onInitializeClient() {
		HostLink.launch();
		ClientTickEvents.END_CLIENT_TICK.register(BlockCraftClient::tick);
		// Ask for the world as soon as the client is up, rather than waiting to observe a particular
		// screen. Matching on TitleScreen was fragile: in a 149-mod profile the title is often replaced
		// or wrapped (main menu mods, modmenu, Realms), so the check could simply never be true and the
		// world was never opened - which is why the guest sat on the menu and never exported a frame.
		ClientLifecycleEvents.CLIENT_STARTED.register(BlockCraftClient::requestWorld);
		ServerPlayConnectionEvents.JOIN.register((handler, sender, server) -> {
			ServerPlayer player = handler.player;
			// floating in creative so the guest player never falls while the host is detached
			player.getAbilities().flying = true;
			player.onUpdateAbilities();
			player.setItemSlot(EquipmentSlot.CHEST, ItemStack.EMPTY);
			setupIn = 10;
		});
		ServerTickEvents.END_SERVER_TICK.register(server -> {
			if (setupIn > 0 && --setupIn == 0) {
				SETUP.forEach(WorldBridge::command);
			}
		});
	}

	/**
	 * Open the passthrough world once, when the client has finished starting.
	 *
	 * <p>Deferred to the render thread: opening a world from a lifecycle callback would run while the
	 * client is still wiring itself up.
	 */
	private static void requestWorld(final Minecraft minecraft) {
		if (Boolean.getBoolean("blockcraft.noAutoWorld")) {
			return;
		}

		BlockCraft.LOG.info("client started; opening the passthrough world");
		minecraft.execute(() -> {
			worldRequested = true;
			openWorld(minecraft);
		});
	}

	private static void tick(final Minecraft minecraft) {
		// a death (the void) would leave the death screen over the host's picture: respawn straight away
		if (minecraft.player != null && minecraft.gui.screen() instanceof DeathScreen && --respawnIn <= 0) {
			respawnIn = 40;
			minecraft.player.respawn();
		}

		if (!configured) {
			configured = true;
			configure(minecraft.options);
		}

		// Fallback for the case where CLIENT_STARTED fired before this was registered (or the world was
		// closed later): any test later than the startup one. Not tied to a screen class any more.
		if (!worldRequested && minecraft.level == null && minecraft.player == null
			&& !Boolean.getBoolean("blockcraft.noAutoWorld")) {
			worldRequested = true;
			openWorld(minecraft);
		}
	}

	/** Settings for sitting behind another game: keep running unfocused, and no sky/cloud/bobbing effects in the picture. */
	private static void configure(final Options options) {
		options.pauseOnLostFocus = false;
		options.onboardAccessibility = false;
		options.tutorialStep = TutorialSteps.NONE;
		options.cloudStatus().set(CloudStatus.OFF);
		options.bobView().set(false);
		options.vignette().set(false);
		options.improvedTransparency().set(false);
		options.inactivityFpsLimit().set(InactivityFpsLimit.MINIMIZED);
		options.fovEffectScale().set(0.0);
		options.damageTiltStrength().set(0.0);
		options.menuBackgroundBlurriness().set(0);
		options.enableVsync().set(false);
		// the host shows ~60-120 fps: rendering faster only competes with it for the GPU
		options.framerateLimit().set(120);
		options.save();
	}

	private static void openWorld(final Minecraft minecraft) {
		if (minecraft.getLevelSource().levelExists(WORLD)) {
			BlockCraft.LOG.info("opening world {}", WORLD);
			minecraft.createWorldOpenFlows().openWorld(WORLD, () -> minecraft.gui.setScreen(new TitleScreen()));
		} else {
			BlockCraft.LOG.info("creating world {}", WORLD);
			LevelSettings settings = new LevelSettings("BlockCraft", GameType.CREATIVE,
				LevelSettings.DifficultySettings.DEFAULT, true, WorldDataConfiguration.DEFAULT);
			minecraft.createWorldOpenFlows().createFreshLevel(WORLD, settings, new WorldOptions(0L, false, false),
				BlockCraftClient::voidWorld, minecraft.gui.screen());
		}
	}

	/** A flat world with a single layer of air: nothing but what gets built (the host's ground arrives as barriers). */
	private static WorldDimensions voidWorld(final HolderLookup.Provider registries) {
		FlatLevelGeneratorSettings flat = new FlatLevelGeneratorSettings(
			Optional.of(HolderSet.direct()),
			registries.lookupOrThrow(Registries.BIOME).getOrThrow(Biomes.PLAINS), List.of()
		);
		flat.getLayersInfo().add(new FlatLayerInfo(1, Blocks.AIR));
		flat.updateLayers();
		return WorldPresets.createNormalWorldDimensions(registries)
			.replaceOverworldGenerator(registries, new FlatLevelSource(flat));
	}
}
