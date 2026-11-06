package dev.sven.blockcraft;

import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * The guest mod, Minecraft Java 26.3 on Fabric.
 *
 * <p>Minecraft is the guest: Outer Wilds (host) owns the camera and the frame; Minecraft owns its own
 * world simulation and exports its rendered layers through POSIX shared memory. See docs/CONTRACT.md
 * in the modding project for the cross-process contract.
 */
public class BlockCraft implements ModInitializer {
	public static final String ID = "blockcraft";
	public static final Logger LOG = LoggerFactory.getLogger(ID);
	/** True while a host game is driving the camera. The integrated server shares this JVM, so both sides read it. */
	public static volatile boolean active;

	@Override
	public void onInitialize() {
		ServerLifecycleEvents.SERVER_STARTED.register(WorldBridge::attach);
		ServerLifecycleEvents.SERVER_STOPPING.register(server -> WorldBridge.detach());
		LOG.info("blockcraft loaded");
	}
}
