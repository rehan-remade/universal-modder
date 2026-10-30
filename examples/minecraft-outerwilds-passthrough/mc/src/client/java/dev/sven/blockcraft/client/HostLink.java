package dev.sven.blockcraft.client;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import dev.sven.blockcraft.BlockCraft;
import dev.sven.blockcraft.WorldBridge;
import java.net.InetSocketAddress;
import java.util.Locale;
import net.minecraft.client.Minecraft;
import org.java_websocket.WebSocket;
import org.java_websocket.handshake.ClientHandshake;
import org.java_websocket.server.WebSocketServer;

/**
 * The host's connection: a WebSocket server on 127.0.0.1 (port 25599, or -Dblockcraft.port).
 *
 * <p>This is the guest half of the state channel in docs/CONTRACT.md. The host (the Outer Wilds OWML
 * mod) is the client; Minecraft is the server, which keeps the reconnect logic in the host where the
 * game loop already retries.
 *
 * <p>Host to Minecraft (JSON, already in Minecraft coordinates):
 * <ul>
 * <li>{"t":"cam","f":frame,"p":[x,y,z],"r":[yaw,pitch,roll],"fov":vertical degrees,"fp":first person,"pl":[feet x,y,z],"h":body yaw}</li>
 * <li>{"t":"ground","c":[x,z,yBottom,yTop, ...]}: solid columns the host knows about, as barriers</li>
 * <li>{"t":"clear"}: remove the barriers placed so far</li>
 * <li>{"t":"cmd","c":"time set noon"}: a server command</li>
 * </ul>
 * Minecraft to host: {"t":"hello","v":1,"shm":"blockcraft-frame","pid":N} on connect, {"t":"bye",...} on stop.
 */
public final class HostLink extends WebSocketServer {
	private static HostLink instance;

	private HostLink(final int port) {
		super(new InetSocketAddress("127.0.0.1", port));
		this.setReuseAddr(true);
		this.setDaemon(true);
	}

	static void launch() {
		int port = Integer.getInteger("blockcraft.port", 25599);
		instance = new HostLink(port);
		instance.start();
	}

	/** Send a message to the host, if one is connected. */
	static void send(final String message) {
		HostLink link = instance;
		if (link == null) {
			return;
		}

		for (WebSocket c : link.getConnections()) {
			if (c.isOpen()) {
				c.send(message);
			}
		}
	}

	@Override
	public void onStart() {
		BlockCraft.LOG.info("host link listening on 127.0.0.1:{}", this.getPort());
	}

	@Override
	public void onOpen(final WebSocket conn, final ClientHandshake handshake) {
		BlockCraft.LOG.info("host connected from {}", conn.getRemoteSocketAddress());
		// A client that connects and immediately drops (a port probe, a host that restarted) is normal
		// and must not take the link down: guard the send and check the connection is still open.
		try {
			if (conn.isOpen()) {
				conn.send(String.format(Locale.ROOT,
					"{\"t\":\"hello\",\"v\":1,\"shm\":\"%s\",\"pid\":%d}",
					FrameExporter.NAME, ProcessHandle.current().pid()));
			}
		} catch (RuntimeException e) {
			BlockCraft.LOG.warn("guest hello not delivered: {}", e.toString());
		}
	}

	@Override
	public void onClose(final WebSocket conn, final int code, final String reason, final boolean remote) {
		BlockCraft.LOG.info("host disconnected ({} {})", code, reason);
	}

	@Override
	public void onMessage(final WebSocket conn, final String message) {
		try {
			JsonObject m = JsonParser.parseString(message).getAsJsonObject();
			switch (m.get("t").getAsString()) {
				case "cam" -> HostState.update(m);
				case "ground" -> WorldBridge.solid(ints(m.getAsJsonArray("c")));
				case "clear" -> WorldBridge.clearSolid();
				case "cmd" -> WorldBridge.command(m.get("c").getAsString());
				default -> Minecraft.getInstance().execute(() -> ClientInput.handle(Minecraft.getInstance(), m));
			}
		} catch (RuntimeException e) {
			BlockCraft.LOG.warn("bad host message {}: {}",
				message.length() > 200 ? message.substring(0, 200) : message, e.toString());
		}
	}

	@Override
	public void onError(final WebSocket conn, final Exception e) {
		// A failed handshake from a bare port probe is routine, and Java-WebSocket reports it here with
		// a full stack per connection. Keep the one-line form so the log stays readable; a real fault
		// still shows its type and message.
		BlockCraft.LOG.warn("host link error: {}", e.toString());
	}

	private static int[] ints(final JsonArray a) {
		int[] out = new int[a.size()];
		for (int i = 0; i < out.length; i++) {
			out[i] = a.get(i).getAsInt();
		}

		return out;
	}
}
