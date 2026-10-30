package dev.sven.blockcraft.client;

import com.google.gson.JsonObject;
import dev.sven.blockcraft.BlockCraft;
import dev.sven.blockcraft.client.mixin.KeyMappingAccessor;
import net.minecraft.client.KeyMapping;
import net.minecraft.client.Minecraft;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.world.entity.player.Inventory;

/**
 * Host input, applied on the client thread: the host window has the focus, so Minecraft never sees these
 * itself.
 *
 * <p>Only the keys this bridge uses: the guest player's body is driven by the host's own movement, so the
 * link carries the handful of interactions the host cannot express as a camera pose.
 */
final class ClientInput {
	private ClientInput() {
	}

	static void handle(final Minecraft minecraft, final JsonObject m) {
		LocalPlayer player = minecraft.player;
		switch (m.get("t").getAsString()) {
			case "key" -> {
				String k = m.get("k").getAsString();
				boolean down = !m.has("down") || m.get("down").getAsBoolean();
				if (k.equals("escape")) {
					if (down && minecraft.gui.screen() != null) {
						minecraft.gui.screen().onClose();
					}

					return;
				}

				KeyMapping key = switch (k) {
					case "use" -> minecraft.options.keyUse;
					case "attack" -> minecraft.options.keyAttack;
					case "pick" -> minecraft.options.keyPickItem;
					case "inventory" -> minecraft.options.keyInventory;
					case "drop" -> minecraft.options.keyDrop;
					case "swap" -> minecraft.options.keySwapOffhand;
					default -> null;
				};
				if (key != null) {
					if (down && !key.isDown()) {
						KeyMappingAccessor access = (KeyMappingAccessor) key;
						access.blockcraft$setClickCount(access.blockcraft$getClickCount() + 1);
					}

					key.setDown(down);
				}
			}
			case "slot" -> {
				if (player != null) {
					player.getInventory().setSelectedSlot(Math.clamp(m.get("n").getAsInt(), 0, Inventory.getSelectionSize() - 1));
				}
			}
			case "scroll" -> {
				if (player != null) {
					Inventory inventory = player.getInventory();
					int size = Inventory.getSelectionSize();
					inventory.setSelectedSlot(Math.floorMod(inventory.getSelectedSlot() - m.get("d").getAsInt(), size));
				}
			}
			case "hud" -> {
				if (minecraft.gui.hud.isHidden() != m.get("hidden").getAsBoolean()) {
					minecraft.gui.hud.toggle();
				}
			}
			case "pin" -> {
				// pin [x y z yaw pitch [fov]]: hold a fixed pose with no host attached, or clear it.
				// Standing debug aid for the frame export: the exporter only runs while a pose is live, and
				// `live()` times out after two seconds, so without this the export can only be looked at
				// while the host is sending. With it the guest exports on its own and can be tested alone.
				if (!m.has("p")) {
					HostState.clearPin();
					BlockCraft.LOG.info("pin cleared");
					return;
				}

				var p = m.getAsJsonArray("p");
				HostState.pin(
					p.get(0).getAsDouble(), p.get(1).getAsDouble(), p.get(2).getAsDouble(),
					p.get(3).getAsFloat(), p.get(4).getAsFloat(),
					p.size() > 5 ? p.get(5).getAsFloat() : 70.0F);
				BlockCraft.LOG.info("pin set({},{},{}) yaw {} pitch {}",
					p.get(0).getAsDouble(), p.get(1).getAsDouble(), p.get(2).getAsDouble(),
					p.get(3).getAsFloat(), p.get(4).getAsFloat());
			}
			default -> BlockCraft.LOG.debug("ignoring host message {}", m.get("t").getAsString());
		}
	}
}
