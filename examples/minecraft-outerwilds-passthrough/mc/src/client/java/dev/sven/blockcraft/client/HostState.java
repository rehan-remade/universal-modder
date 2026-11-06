package dev.sven.blockcraft.client;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import dev.sven.blockcraft.BlockCraft;

/**
 * The host's latest camera and player pose, already converted into Minecraft coordinates by the host.
 *
 * <p>Outer Wilds owns the camera (docs/CONTRACT.md, "Ownership"), so every frame this class hands the
 * render a pose that came from the host, and Minecraft renders its own world from it. When no pose has
 * arrived for {@link #TIMEOUT_NANOS} the guest detaches and renders from its own camera.
 */
public final class HostState {
	/**
	 * @param hostFrame the host's frame number for this pose (echoed in the exported frame)
	 * @param x camera position in Minecraft coordinates
	 * @param yaw Minecraft yaw (0 faces +Z, clockwise from above), pitch (positive looks down), roll
	 * @param fov vertical field of view, degrees
	 * @param firstPerson whether the host camera is first person (third person shows the player model)
	 * @param drive legacy from the GTA V example; this bridge lets the host drive the player
	 * @param position feet position of the player, used to place the body in third person
	 * @param bodyYaw the player body's yaw, so the model faces where the host looks
	 * @param receivedNanos our own monotonic clock when this pose arrived
	 */
	public record Pose(
		long hostFrame, double x, double y, double z, float yaw, float pitch, float roll, float fov,
		boolean firstPerson, double px, double py, double pz, float bodyYaw, long receivedNanos,
		boolean drive
	) {
	}

	private static final long TIMEOUT_NANOS = 2_000_000_000L;
	private static volatile Pose latest;
	/** A pose pinned by the `pin` dev message, which outlives the host's timeout. See ClientInput. */
	private static volatile Pose pinned;
	/** The pose this frame renders with, taken once per frame so every hook agrees. Render thread only. */
	private static Pose frame;

	private HostState() {
	}

	/** Hold a fixed pose with no host attached (dev aid; `pin` message). */
	static void pin(final double x, final double y, final double z,
		final float yaw, final float pitch, final float fov) {
		pinned = new Pose(0L, x, y, z, yaw, pitch, 0.0F, fov, true,
			x, y - 1.62, z, yaw, System.nanoTime(), false);
	}

	static void clearPin() {
		pinned = null;
	}

	/** {"t":"cam","f":frame,"p":[x,y,z],"r":[yaw,pitch,roll],"fov":deg,"fp":bool,"pl":[x,y,z],"h":bodyYaw} */
	static void update(final JsonObject m) {
		JsonArray p = m.getAsJsonArray("p");
		JsonArray r = m.getAsJsonArray("r");
		JsonArray pl = m.has("pl") ? m.getAsJsonArray("pl") : p;
		float yaw = r.get(0).getAsFloat();
		latest = new Pose(
			m.has("f") ? m.get("f").getAsLong() : 0L,
			p.get(0).getAsDouble(), p.get(1).getAsDouble(), p.get(2).getAsDouble(),
			yaw, r.get(1).getAsFloat(), r.size() > 2 ? r.get(2).getAsFloat() : 0.0F,
			m.has("fov") ? m.get("fov").getAsFloat() : 70.0F,
			!m.has("fp") || m.get("fp").getAsBoolean(),
			pl.get(0).getAsDouble(), pl.get(1).getAsDouble(), pl.get(2).getAsDouble(),
			m.has("h") ? m.get("h").getAsFloat() : yaw,
			System.nanoTime(),
			m.has("drive") && m.get("drive").getAsBoolean()
		);
	}

	/** The latest pose if the host is still sending, else null. A pinned pose always wins. */
	static Pose live() {
		Pose p = pinned;
		if (p != null) {
			return p;
		}

		p = latest;
		return p != null && System.nanoTime() - p.receivedNanos() < TIMEOUT_NANOS ? p : null;
	}

	/** The pose for the frame being rendered, or null when no host is attached. */
	public static Pose frame() {
		return frame;
	}

	public static void beginFrame() {
		frame = live();
		BlockCraft.active = frame != null;
	}
}
