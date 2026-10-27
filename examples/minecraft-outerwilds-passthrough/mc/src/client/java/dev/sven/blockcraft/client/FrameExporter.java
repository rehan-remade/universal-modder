package dev.sven.blockcraft.client;

import com.mojang.blaze3d.pipeline.RenderTarget;
import com.mojang.blaze3d.systems.RenderSystem;
import dev.sven.blockcraft.BlockCraft;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.VarHandle;

/**
 * Hands Minecraft's frame to Outer Wilds through the POSIX shared mapping {@code blockcraft-frame}
 * ({@code /dev/shm/blockcraft-frame}, which the host opens as {@code Z:\dev\shm\blockcraft-frame}).
 *
 * <p>The layout is fixed by {@code docs/CONTRACT.md}; both sides spell it out by hand, so any change
 * here is a {@link #VERSION} bump there too.
 *
 * <pre>
 * header (4096 bytes, little-endian)
 *   0 u32 magic "BCFF"   4 u32 version   8 u32 header bytes 4096   12 u32 slot count 3
 *   16 u64 slot stride   24 u32 max width   28 u32 max height
 *   32 u64 publish counter (- bumped after a slot is complete)   40 i32 latest slot (-1 none)   44 i32 guest pid
 *   256 + 128*i: slot i
 *     +0 u64 seq (odd while being written)   +8 u64 guest frame   +16 u64 host frame
 *     +24 u32 width   +28 u32 height   +32 f32 near   +36 f32 far   +40 f32 vertical fov (deg)
 *     +44 u32 flags: 1 = depth in [0,1], 2 = rows bottom-up, 4 = reversed Z
 *     +48 f64 cam x   +56 y   +64 z   +72 f32 yaw   +76 pitch   +80 roll   +84 i32 first person
 *     +88 u64 capture nanos   +96 u64 publish nanos
 * slot i pixels at 4096 + i*stride, each layer width*height*4:
 *   world colour RGBA8 | world depth f32 | overlay RGBA8
 * </pre>
 *
 * <p>The world layer is read just before the hand is drawn and the overlay is read at the end of the
 * frame, so what lands between them (hand, screen effects, GUI) becomes the overlay. Both are read with
 * a framebuffer of our own rather than through Minecraft's command encoder; {@link #readTexture} explains
 * why that is necessary.
 */
public final class FrameExporter {
	/** The POSIX object name. Mirrored in docs/CONTRACT.md and the host's FrameReader. */
	public static final String NAME = "blockcraft-frame";
	/** Diagnostic: log the camera-override path for the first few frames and then every 300th. */
	private static final int MAGIC = 0x46464342; // "BCFF" little-endian
	private static final int VERSION = 1;
	private static final int HEADER = 4096;
	private static final int SLOTS = 3;
	private static final int SLOT_DESC = 256;
	private static final int SLOT_DESC_BYTES = 128;
	private static final int MAX_W = 3840;
	private static final int MAX_H = 2160;
	private static final long LAYER_MAX = (long) MAX_W * MAX_H * 4;
	private static final long STRIDE = LAYER_MAX * 3;
	private static final ValueLayout.OfInt INT = ValueLayout.JAVA_INT_UNALIGNED;
	private static final ValueLayout.OfLong LONG = ValueLayout.JAVA_LONG_UNALIGNED;
	private static final ValueLayout.OfFloat FLOAT = ValueLayout.JAVA_FLOAT_UNALIGNED;
	private static final ValueLayout.OfDouble DOUBLE = ValueLayout.JAVA_DOUBLE_UNALIGNED;
	/** Near/far of the frame being rendered (the camera sets far each frame). */
	private static final float NEAR = 0.05F;
	private static float far = 1024.0F;
	/** How long a capture may wait for its copies before publishing what it has. */
	private static final long STALE_NANOS = 250_000_000L;

	private static SharedMemory shm;
	private static boolean failed;
	private static boolean warnedSize;
	/**
	 * The single capture buffer set. There is deliberately only one: with several, only the first ever
	 * received data from {@code copyTextureToBuffer}, and the host saw an empty picture in two of the
	 * three slots. One capture, one set of buffers, and {@link Capture#busy} throttles to the GPU's pace.
	 */
	private static Capture capture;
	/** The shm slot the single capture publishes into; rotated so the host never reads what is written. */
	private static int nextSlot;
	private static long frameCounter;
	private static long publishCounter;
	private static Capture current;

	private FrameExporter() {
	}

	private static final class Capture {
		java.nio.ByteBuffer color;
		java.nio.ByteBuffer depth;
		java.nio.ByteBuffer overlay;
		int width;
		int height;
		long generation;
		boolean busy;
		long busySince;
		HostState.Pose pose;
		float far;
		long frame;
		long captureNanos;
		/** Layers still outstanding; the capture publishes when this reaches zero. */
		int pending;
		boolean overlayQueued;
		/** Wall-clock deadline after which an unfinished capture publishes anyway (see expireStale). */
		long deadline;

		void allocate(final int w, final int h) {
			this.free();
			this.color = org.lwjgl.BufferUtils.createByteBuffer(w * h * 4);
			this.depth = org.lwjgl.BufferUtils.createByteBuffer(w * h * 4);
			this.overlay = org.lwjgl.BufferUtils.createByteBuffer(w * h * 4);
			this.width = w;
			this.height = h;
		}

		void free() {
			this.color = this.depth = this.overlay = null;
		}
	}

	/**
	 * Read a render target's texture with raw GL, through a framebuffer set up here.
	 *
	 * <p>Minecraft's own {@code CommandEncoder.copyTextureToBuffer} cannot be used from a render hook:
	 * its backend reads through a <em>cached</em> read framebuffer and, in this session, that framebuffer
	 * is left attached to something else, so every read comes back as the same all-zero image. Vanilla's
	 * own screenshot path fails here for the same reason (measured: {@code Screenshot.takeScreenshot} on
	 * {@code mainRenderTarget} returns a pure-black 1280x720 image with hash 9139525410424356864 on every
	 * frame, while a raw read of the same texture at the same moment returns 921600/921600 non-black
	 * pixels). Binding our own framebuffer and reading with {@code glReadPixels} returns the picture.
	 *
	 * @param texture Minecraft's GPU texture
	 * @param dst where the pixels are written, {@code width*height*4} bytes, RGBA8
	 * @param depth whether to attach as the depth attachment (otherwise colour attachment 0)
	 * @return true if the read completed
	 */
	private static boolean readTexture(final com.mojang.renderpearl.api.textures.GpuTexture texture,
		final java.nio.ByteBuffer dst, final int width, final int height, final boolean depth) {
		if (!(texture instanceof com.mojang.renderpearl.backend.opengl.GlTexture gl)) {
			return false;
		}

		int previous = org.lwjgl.opengl.GL11.glGetInteger(org.lwjgl.opengl.GL30.GL_FRAMEBUFFER_BINDING);
		int fbo = org.lwjgl.opengl.GL30.glGenFramebuffers();

		try {
			org.lwjgl.opengl.GL30.glBindFramebuffer(org.lwjgl.opengl.GL30.GL_FRAMEBUFFER, fbo);
			org.lwjgl.opengl.GL30.glFramebufferTexture2D(org.lwjgl.opengl.GL30.GL_FRAMEBUFFER,
				depth ? org.lwjgl.opengl.GL30.GL_DEPTH_ATTACHMENT : org.lwjgl.opengl.GL30.GL_COLOR_ATTACHMENT0,
				org.lwjgl.opengl.GL11.GL_TEXTURE_2D, gl.glId(), 0);
			if (depth) {
				// A depth-only framebuffer has no colour attachment, so the read buffer must be NONE.
				org.lwjgl.opengl.GL11.glReadBuffer(org.lwjgl.opengl.GL11.GL_NONE);
			}

			if (org.lwjgl.opengl.GL30.glCheckFramebufferStatus(org.lwjgl.opengl.GL30.GL_FRAMEBUFFER)
				!= org.lwjgl.opengl.GL30.GL_FRAMEBUFFER_COMPLETE) {
				return false;
			}

			dst.clear();
			org.lwjgl.opengl.GL11.glReadPixels(0, 0, width, height,
				depth ? org.lwjgl.opengl.GL11.GL_DEPTH_COMPONENT : org.lwjgl.opengl.GL11.GL_RGBA,
				depth ? org.lwjgl.opengl.GL11.GL_FLOAT : org.lwjgl.opengl.GL11.GL_UNSIGNED_BYTE, dst);
			dst.position(0);
			dst.limit(width * height * 4);
			return true;
		} finally {
			org.lwjgl.opengl.GL30.glBindFramebuffer(org.lwjgl.opengl.GL30.GL_FRAMEBUFFER, previous);
			org.lwjgl.opengl.GL30.glDeleteFramebuffers(fbo);
		}
	}

	public static void setFar(final float depthFar) {
		far = depthFar;
	}

	public static boolean exporting() {
		return shm != null;
	}

	private static boolean ensureShm() {
		if (shm != null) {
			return true;
		}

		if (failed) {
			return false;
		}

		try {
			shm = SharedMemory.create(NAME, HEADER + STRIDE * SLOTS);
			MemorySegment m = shm.segment;
			m.set(INT, 0, MAGIC);
			m.set(INT, 4, VERSION);
			m.set(INT, 8, HEADER);
			m.set(INT, 12, SLOTS);
			m.set(LONG, 16, STRIDE);
			m.set(INT, 24, MAX_W);
			m.set(INT, 28, MAX_H);
			m.set(INT, 40, -1);
			m.set(INT, 44, (int) ProcessHandle.current().pid());
			BlockCraft.LOG.info("frame export: /dev/shm/{} ({} MB) - host reads it as Z:\\dev\\shm\\{}",
				NAME, (HEADER + STRIDE * SLOTS) >> 20, NAME);
			return true;
		} catch (Throwable t) {
			failed = true;
			BlockCraft.LOG.error("frame export disabled: could not create /dev/shm/" + NAME, t);
			return false;
		}
	}

	/** GameRenderer.renderLevel, just before the 3D HUD (hand): copy the world layer, then clear colour. */
	public static void captureWorld(final RenderTarget target) {
		current = null;
		HostState.Pose pose = HostState.frame();
		if (pose == null || !ensureShm()) {
			return;
		}

		int w = target.width;
		int h = target.height;
		if ((long) w * h * 4 > LAYER_MAX) {
			if (!warnedSize) {
				warnedSize = true;
				BlockCraft.LOG.warn("frame export: {}x{} exceeds {}x{}, not exporting", w, h, MAX_W, MAX_H);
			}

			return;
		}

		Capture c = capture;
		if (c == null) {
			c = capture = new Capture();
		}

		long now = System.nanoTime();
		if (c.busy) {
			// The previous capture is still in flight. Export nothing this frame rather than start a second
			// one: a single capture keeps the copy target unambiguous, which is the whole point. The rate
			// the GPU retires a capture at is the export rate, and a slower picture beats a torn one.
			expireStale();
			if (c.busy) {
				return;
			}
		}

		if (c.width != w || c.height != h || c.color == null) {
			c.allocate(w, h);
		}

		c.generation++;
		c.busy = true;
		c.busySince = now;
		c.pose = pose;
		c.far = far;
		c.frame = ++frameCounter;
		c.captureNanos = now;
		final Capture cap = c;
		final long gen = cap.generation;
		// The world layer is read here; the overlay is read at the end of GameRenderer.render, so the
		// capture is only complete once both have. If the overlay hook never runs for this frame, the
		// deadline below publishes what there is rather than wedging the exporter.
		cap.pending = 2;
		cap.overlayQueued = false;
		cap.deadline = now + STALE_NANOS;
		// Read synchronously. There is no command encoder involved: see readTexture for why Minecraft's
		// copyTextureToBuffer cannot be used from a render hook.
		if (!readTexture(target.getColorTexture(), cap.color, w, h, false)
			|| !readTexture(target.getDepthTexture(), cap.depth, w, h, true)) {
			cap.busy = false;
			return;
		}

		arrive(cap, gen);
		arrive(cap, gen);
		current = cap;
	}

	/** One of a capture's layers is ready. Publish when all have. */
	private static void arrive(final Capture c, final long generation) {
		if (c.generation != generation || !c.busy) return;
		if (--c.pending > 0) {
			return;
		}

		publish(c);
	}

	/** Publish any capture that has been waiting too long, so a skipped overlay hook cannot wedge us. */
	private static void expireStale() {		Capture c = capture;
		if (c == null || !c.busy) {
			return;
		}

		if (System.nanoTime() < c.deadline) {
			return;
		}

		// Whatever layers did not arrive are reported as empty rather than blocking the exporter.
		BlockCraft.LOG.warn("frame export: capture expired with {} layers outstanding (overlay queued {})",
			c.pending, c.overlayQueued);
		c.pending = 0;
		publish(c);
	}

	/** End of GameRenderer.render: the overlay (hand, screen effects, GUI) is complete. */
	public static void captureOverlay(final RenderTarget target) {
		Capture c = current;
		current = null;
		if (c == null) {
			return;
		}

		if (target.width != c.width || target.height != c.height) {
			c.busy = false;
			return;
		}

		long generation = c.generation;
		c.overlayQueued = true;
		if (!readTexture(target.getColorTexture(), c.overlay, c.width, c.height, false)) {
			c.busy = false;
			return;
		}

		arrive(c, generation);
	}

	private static void publish(final Capture c) {
		try {
			MemorySegment m = shm.segment;
			int slot = nextSlot;
			nextSlot = (nextSlot + 1) % SLOTS;
			long desc = SLOT_DESC + (long) SLOT_DESC_BYTES * slot;
			long seq = m.get(LONG, desc);
			if ((seq & 1L) != 0L) {
				seq++;
			}

			m.set(LONG, desc, seq + 1L);
			VarHandle.fullFence();
			long base = HEADER + STRIDE * slot;
			long n = (long) c.width * c.height * 4;
			copy(c.color, m, base, n);
			copy(c.depth, m, base + n, n);
			copy(c.overlay, m, base + 2 * n, n);
			HostState.Pose p = c.pose;
			m.set(LONG, desc + 8, c.frame);
			m.set(LONG, desc + 16, p.hostFrame());
			m.set(INT, desc + 24, c.width);
			m.set(INT, desc + 28, c.height);
			m.set(FLOAT, desc + 32, NEAR);
			m.set(FLOAT, desc + 36, c.far);
			m.set(FLOAT, desc + 40, p.fov());
			m.set(INT, desc + 44, (RenderSystem.getDevice().getDeviceInfo().isZZeroToOne() ? 1 : 0) | 2 | 4);
			m.set(DOUBLE, desc + 48, p.x());
			m.set(DOUBLE, desc + 56, p.y());
			m.set(DOUBLE, desc + 64, p.z());
			m.set(FLOAT, desc + 72, p.yaw());
			m.set(FLOAT, desc + 76, p.pitch());
			m.set(FLOAT, desc + 80, p.roll());
			m.set(INT, desc + 84, p.firstPerson() ? 1 : 0);
			m.set(LONG, desc + 88, c.captureNanos);
			m.set(LONG, desc + 96, System.nanoTime());
			VarHandle.fullFence();
			m.set(LONG, desc, seq + 2L);
			m.set(INT, 40, slot);
			VarHandle.fullFence();
			m.set(LONG, 32, ++publishCounter);
		} catch (RuntimeException e) {
			BlockCraft.LOG.warn("frame export failed", e);
		} finally {
			c.busy = false;
		}
	}

	private static void copy(final java.nio.ByteBuffer src, final MemorySegment dst, final long offset, final long n) {
		MemorySegment.copy(MemorySegment.ofBuffer(src), 0L, dst, offset, n);
	}
}
