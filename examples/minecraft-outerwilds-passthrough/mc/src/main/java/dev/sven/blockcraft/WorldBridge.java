package dev.sven.blockcraft;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;

/**
 * Server-side half: the host's ground arrives as invisible barrier blocks, and commands are run on the
 * integrated server.
 *
 * <p>Per docs/CONTRACT.md, Outer Wilds owns the ground the player stands on and Minecraft owns its own
 * simulation. The host sends the solid columns it knows about; here they become barriers so the guest
 * player can collide with the same terrain the host is standing on. Barriers are tracked so a reset
 * only ever removes the blocks we placed, never anything the player built.
 */
public final class WorldBridge {
	private static volatile MinecraftServer server;
	/** Barriers we placed (so a reset only removes ours, never the player's builds). */
	private static final Set<BlockPos> barriers = ConcurrentHashMap.newKeySet();

	private WorldBridge() {
	}

	public static void attach(final MinecraftServer s) {
		server = s;
	}

	public static void detach() {
		server = null;
		barriers.clear();
	}

	public static boolean ready() {
		return server != null;
	}

	/**
	 * Columns of solid ground from the host: {x, z, yBottom, yTop, ...} in block coordinates, inclusive.
	 * Only air is replaced, so the player's own builds are never overwritten.
	 */
	public static void solid(final int[] columns) {
		MinecraftServer s = server;
		if (s == null) {
			return;
		}

		s.execute(() -> {
			ServerLevel level = s.overworld();
			BlockState barrier = Blocks.BARRIER.defaultBlockState();
			BlockPos.MutableBlockPos pos = new BlockPos.MutableBlockPos();
			for (int i = 0; i + 3 < columns.length; i += 4) {
				for (int y = columns[i + 2]; y <= columns[i + 3]; y++) {
					pos.set(columns[i], y, columns[i + 1]);
					if (level.isInWorldBounds(pos) && level.getBlockState(pos).isAir()) {
						level.setBlock(pos, barrier, Block.UPDATE_CLIENTS | Block.UPDATE_KNOWN_SHAPE);
						barriers.add(pos.immutable());
					}
				}
			}
		});
	}

	/** Remove every barrier we placed (e.g. when the host teleports somewhere else, or detaches). */
	public static void clearSolid() {
		MinecraftServer s = server;
		if (s == null) {
			return;
		}

		s.execute(() -> {
			ServerLevel level = s.overworld();
			for (BlockPos pos : barriers) {
				if (level.getBlockState(pos).is(Blocks.BARRIER)) {
					level.setBlock(pos, Blocks.AIR.defaultBlockState(), Block.UPDATE_CLIENTS | Block.UPDATE_KNOWN_SHAPE);
				}
			}

			barriers.clear();
		});
	}

	/** Run a command as the server (op). Results go to the log, not to chat (send_command_feedback is off). */
	public static void command(final String command) {
		MinecraftServer s = server;
		if (s == null) {
			return;
		}

		s.execute(() -> {
			BlockCraft.LOG.info("command: {}", command);
			s.getCommands().performPrefixedCommand(s.createCommandSourceStack(), command);
		});
	}
}
