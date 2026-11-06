"""Minimal WebSocket client for the guest's frame link. Shared by the probe tools (not shipped).

The guest speaks the same JSON the Outer Wilds mod sends, so these helpers are deliberately tiny: enough
to handshake, send a masked text frame, and read one back. A full WebSocket library would be more code
than the protocol needs here.
"""
import base64
import json
import os
import socket
import struct

PORT = int(os.environ.get("BLOCKCRAFT_PORT", "25599"))


def connect(timeout=5.0):
    """Open a socket to the guest and complete the WebSocket upgrade."""
    sock = socket.create_connection(("127.0.0.1", PORT), timeout=timeout)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{PORT}\r\nUpgrade: websocket\r\n"
        f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(req.encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise SystemExit("connection closed during handshake")
        buf += chunk
    head, _, rest = buf.partition(b"\r\n\r\n")
    if b"101" not in head.split(b"\r\n")[0]:
        raise SystemExit("handshake failed:\n" + head.decode(errors="replace"))
    return sock


def handshake(sock):
    """Backwards-compatible alias: some callers use connect() when they want the leftover bytes."""
    return connect()


def send_text(sock, text):
    """Client-to-server frames must be masked."""
    payload = text.encode()
    mask = os.urandom(4)
    n = len(payload)
    header = b"\x81"
    if n < 126:
        header += bytes([0x80 | n])
    elif n < 65536:
        header += bytes([0x80 | 126]) + struct.pack("!H", n)
    else:
        header += bytes([0x80 | 127]) + struct.pack("!Q", n)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    sock.sendall(header + mask + masked)


def recv_frame(sock, timeout=3.0):
    """Read one text frame, or None on timeout/close."""
    sock.settimeout(timeout)
    try:
        b = sock.recv(2)
    except socket.timeout:
        return None
    if len(b) < 2:
        return None
    length = b[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", sock.recv(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", sock.recv(8))[0]
    data = b""
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            break
        data += chunk
    return data.decode(errors="replace")


def cam_message(i):
    """The shape the host sends: t, f, p, r, fov, fp, pl, h (see docs/CONTRACT.md)."""
    t = i / 30.0
    return json.dumps({
        "t": "cam",
        "f": i,
        "p": [0.5, 66.0, 0.5],
        "r": [t * 20.0 % 360.0, -5.0, 0.0],
        "fov": 70.0,
        "fp": True,
        "pl": [0.5, 65.0, 0.5],
        "h": 0.0,
    })
