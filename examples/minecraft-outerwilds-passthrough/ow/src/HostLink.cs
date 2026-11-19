using System;
using System.Collections.Concurrent;
using System.IO;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace BlockCraft;

/// <summary>
/// The guest link: a WebSocket client to Minecraft's server on 127.0.0.1:25599 (docs/CONTRACT.md).
///
/// Written by hand rather than with a WebSocket library: OWML ships Newtonsoft but no WebSocket
/// package, and pulling one into a Mono process under Proton is more risk than ~200 lines of RFC 6455
/// framing. Only text frames in both directions are needed.
///
/// Threading: the socket thread only enqueues parsed messages; the game thread drains them. Nothing
/// here touches Unity objects.
/// </summary>
public sealed class HostLink : IDisposable
{
	public const int Port = 25599;

	private readonly ConcurrentQueue<JObject> _inbox = new();
	private readonly ConcurrentQueue<string> _outbox = new();
	private Thread _thread;
	private volatile bool _running;
	private Socket _socket;

	/// <summary>True while a guest is attached and has answered the handshake.</summary>
	public volatile bool Connected;
	public volatile string GuestShm = "blockcraft-frame";
	public volatile int GuestPid;
	public long Sent, Received, Errors;

	public void Start()
	{
		if (_running) return;
		_running = true;
		_thread = new Thread(Loop) { IsBackground = true, Name = "BlockCraft link" };
		_thread.Start();
	}

	/// <summary>Queue a JSON message for the guest (game thread safe).</summary>
	public void Send(JObject message) => _outbox.Enqueue(message.ToString(Formatting.None));

	/// <summary>Drain messages arrived since the last call (game thread).</summary>
	public int Drain(Action<JObject> handler)
	{
		var n = 0;
		while (_inbox.TryDequeue(out var m))
		{
			handler(m);
			n++;
		}
		return n;
	}

	// --- socket thread ----------------------------------------------------------------------------

	private void Loop()
	{
		while (_running)
		{
			try
			{
				Connect();
				Pump();
			}
			catch (Exception e)
			{
				Errors++;
				// Quiet: while no guest is attached this fires once a second, and logging every one of
				// those is what flooded the console and stalled the game. Only a change is reported.
				BlockCraftMod.LogQuiet($"link: {e.Message}");
			}
			finally
			{
				Connected = false;
				try { _socket?.Dispose(); } catch { }
				_socket = null;
			}

			if (_running)
			{
				Thread.Sleep(1000); // the guest may not be up yet; retry quietly
			}
		}
	}

	private void Connect()
	{
		var s = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp)
		{
			NoDelay = true,
			// A frame header can arrive before its payload, and a wedged ReadFully would stall the whole
			// socket thread. Every read is bounded instead: a timeout unwinds to Loop(), which reconnects.
			ReceiveTimeout = 5000
		};
		s.Connect("127.0.0.1", Port);

		var key = Convert.ToBase64String(Guid.NewGuid().ToByteArray());
		var request =
			$"GET / HTTP/1.1\r\nHost: 127.0.0.1:{Port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" +
			$"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n";
		s.Send(Encoding.ASCII.GetBytes(request));
		var response = ReadHttpResponse(s);
		if (!response.Contains("101"))
		{
			throw new IOException("handshake rejected: " + response.Split('\n')[0].Trim());
		}

		_socket = s;
		Connected = true;
		BlockCraftMod.LogResetQuiet();
		BlockCraftMod.Log("link: connected to Minecraft");
	}

	private static string ReadHttpResponse(Socket s)
	{
		var sb = new StringBuilder();
		var buf = new byte[1];
		while (sb.Length < 4096)
		{
			if (s.Receive(buf) == 0) break;
			sb.Append((char)buf[0]);
			if (sb.Length >= 4 && sb.ToString(sb.Length - 4, 4) == "\r\n\r\n") break;
		}
		return sb.ToString();
	}

	private void Pump()
	{
		var s = _socket;
		var header = new byte[2];
		var mask = new byte[4];

		while (_running && s.Connected)
		{
			// Outgoing: text frames, client-masked.
			while (_outbox.TryDequeue(out var text))
			{
				SendTextFrame(s, text);
				Sent++;
			}

			// Incoming. Wait for readability rather than spinning on `Available`: when the guest exits
			// the socket goes to CLOSE-WAIT and Socket.Connected stays true (it reflects the last I/O,
			// not the peer), so a spin on `Available < 2` never sees the FIN, never calls Receive()
			// (and so never trips ReceiveTimeout), and the thread is wedged for good — the host will not
			// reattach until the game restarts. Poll() does see it: readable with nothing to read is a
			// closed peer.
			if (s.Available < 2)
			{
				if (!s.Poll(50_000, SelectMode.SelectRead)) // microseconds; 50 ms
				{
					continue; // nothing yet, but service the outbox again
				}

				if (s.Available == 0)
				{
					throw new IOException("socket closed by the guest");
				}
			}

			ReadFully(s, header, 0, 2);
			var opcode = header[0] & 0x0F;
			var length = (long)(header[1] & 0x7F);
			var masked = (header[1] & 0x80) != 0;
			if (length == 126)
			{
				var b = new byte[2];
				ReadFully(s, b, 0, 2);
				length = (b[0] << 8) | b[1];
			}
			else if (length == 127)
			{
				var b = new byte[8];
				ReadFully(s, b, 0, 8);
				length = 0;
				for (var i = 0; i < 8; i++) length = (length << 8) | b[i];
			}
			if (masked) ReadFully(s, mask, 0, 4);
			if (length < 0 || length > 8 * 1024 * 1024)
			{
				throw new IOException("bad frame length " + length);
			}

			var payload = new byte[length];
			ReadFully(s, payload, 0, (int)length);
			if (masked)
			{
				for (long i = 0; i < length; i++) payload[i] ^= mask[i & 3];
			}

			switch (opcode)
			{
				case 0x1: // text
				case 0x2:
					Received++;
					try
					{
						_inbox.Enqueue(JObject.Parse(Encoding.UTF8.GetString(payload)));
					}
					catch (JsonException e)
					{
						BlockCraftMod.Log("link: bad JSON from guest: " + e.Message);
					}
					break;
				case 0x8: // close
					BlockCraftMod.Log("link: guest closed the connection");
					s.Shutdown(SocketShutdown.Both);
					return;
				case 0x9: // ping
					SendControlFrame(s, 0xA, payload);
					break;
				case 0xA: // pong
					break;
			}
		}
	}

	private static void ReadFully(Socket s, byte[] buf, int offset, int count)
	{
		var got = 0;
		while (got < count)
		{
			var n = s.Receive(buf, offset + got, count - got, SocketFlags.None);
			if (n == 0) throw new IOException("socket closed mid-frame");
			got += n;
		}
	}

	private static void SendTextFrame(Socket s, string text)
	{
		var payload = Encoding.UTF8.GetBytes(text);
		SendFrame(s, 0x1, payload);
	}

	private static void SendControlFrame(Socket s, int opcode, byte[] payload) => SendFrame(s, opcode, payload);

	private static void SendFrame(Socket s, int opcode, byte[] payload)
	{
		var mask = new byte[4];
		new Random().NextBytes(mask);
		var header = new MemoryStream();
		header.WriteByte((byte)(0x80 | opcode));
		var len = payload.Length;
		if (len < 126)
		{
			header.WriteByte((byte)(0x80 | len));
		}
		else if (len <= 0xFFFF)
		{
			header.WriteByte(0x80 | 126);
			header.WriteByte((byte)(len >> 8));
			header.WriteByte((byte)(len & 0xFF));
		}
		else
		{
			header.WriteByte(0x80 | 127);
			for (var i = 7; i >= 0; i--) header.WriteByte((byte)((long)len >> (8 * i) & 0xFF));
		}
		header.Write(mask, 0, 4);
		var frame = new byte[header.Length + len];
		header.Position = 0;
		header.Read(frame, 0, (int)header.Length);
		for (var i = 0; i < len; i++) frame[header.Length + i] = (byte)(payload[i] ^ mask[i & 3]);
		lock (s) s.Send(frame);
	}

	public void Dispose()
	{
		_running = false;
		try { _socket?.Shutdown(SocketShutdown.Both); } catch { }
		try { _socket?.Dispose(); } catch { }
	}
}
