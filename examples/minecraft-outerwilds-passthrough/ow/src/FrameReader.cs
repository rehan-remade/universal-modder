using System;
using System.IO;
using System.IO.MemoryMappedFiles;
using System.Threading;

namespace BlockCraft;

/// <summary>
/// The guest's frame mapping. Minecraft writes a triple-buffered, seqlocked set of layers into a POSIX
/// shared memory object; inside the Proton prefix that object is a file at Z:\dev\shm\&lt;name&gt;, so an
/// ordinary MemoryMappedFile opens it (proven by the transport probe, 2026-10-19).
///
/// Layout is fixed by docs/CONTRACT.md. Never change an offset here without bumping the version there.
/// </summary>
public sealed class FrameReader : IDisposable
{
	public const uint Magic = 0x46464342; // "BCFF" little-endian
	public const int Version = 1;
	public const int HeaderBytes = 4096;
	public const int SlotCount = 3;
	public const int SlotDescBytes = 128;
	public const int SlotDescBase = 256;
	public const int Layers = 3; // world colour, world depth, overlay

	private readonly MemoryMappedFile _mmf;
	private readonly MemoryMappedViewAccessor _view;
	private readonly byte[] _header = new byte[HeaderBytes];

	public long SlotStride { get; private set; }
	public int MaxWidth { get; private set; }
	public int MaxHeight { get; private set; }
	public int GuestPid { get; private set; }

	/// <summary>One fully-read frame. Buffers are reused between calls unless <paramref name="copy"/> is set.</summary>
	public sealed class Frame
	{
		public long Seq;
		public long GuestFrame;
		public long HostFrame;
		public int Width;
		public int Height;
		public float Near;
		public float Far;
		public float Fov;
		public uint Flags;
		public double CamX, CamY, CamZ;
		public float Yaw, Pitch, Roll;
		public bool FirstPerson;
		public long CaptureNanos;
		public long PublishNanos;
		/// <summary>Row-major RGBA8, top-left origin, premultiplied alpha.</summary>
		public byte[] Colour;
		/// <summary>Row-major float32 depth, same orientation as Colour.</summary>
		public byte[] Depth;
		/// <summary>Row-major RGBA8 hand + HUD, premultiplied alpha.</summary>
		public byte[] Overlay;

		public bool DepthZeroToOne => (Flags & 1u) != 0u;
		public bool RowsBottomUp => (Flags & 2u) != 0u;
		public bool ReversedZ => (Flags & 4u) != 0u;
	}

	/// <summary>Counters for the diagnostics overlay and the log.</summary>
	public long Reads, Torn, Missed, WrongMagic;

	private FrameReader(MemoryMappedFile mmf, MemoryMappedViewAccessor view)
	{
		_mmf = mmf;
		_view = view;
	}

	/// <summary>Open the guest's mapping by its POSIX name (without the leading slash). Throws if absent.</summary>
	public static FrameReader Open(string posixName)
	{
		// Wine maps Z:\ to / ; the shm object is a file under /dev/shm.
		var winPath = @"Z:\dev\shm\" + posixName.Replace('/', '\\');
		FileStream fs;
		try
		{
			fs = new FileStream(winPath, FileMode.Open, FileAccess.ReadWrite, FileShare.ReadWrite, 1, FileOptions.RandomAccess);
		}
		catch (IOException)
		{
			throw new IOException($"could not open {winPath} (is the Minecraft mod running?)");
		}

		var length = fs.Length;
		if (length < HeaderBytes)
		{
			fs.Dispose();
			throw new IOException($"{winPath} is only {length} bytes");
		}

		var mmf = MemoryMappedFile.CreateFromFile(fs, null, length, MemoryMappedFileAccess.ReadWrite,
			HandleInheritability.None, false);
		fs.Dispose();
		var view = mmf.CreateViewAccessor(0, length, MemoryMappedFileAccess.ReadWrite);
		var reader = new FrameReader(mmf, view);
		reader.ReadHeader();
		return reader;
	}

	/// <summary>True once the header magic/version match; a stale or foreign object is rejected, never misread.</summary>
	public bool IsCompatible { get; private set; }

	private void ReadHeader()
	{
		_view.ReadArray(0, _header, 0, HeaderBytes);
		var magic = BitConverter.ToUInt32(_header, 0);
		var version = BitConverter.ToInt32(_header, 4);
		if (magic != Magic || version != Version)
		{
			WrongMagic++;
			IsCompatible = false;
			BlockCraftMod.Log($"frame mapping rejected: magic 0x{magic:X8} version {version} " +
				$"(expected 0x{Magic:X8} v{Version})");
			return;
		}

		IsCompatible = true;
		SlotStride = BitConverter.ToInt64(_header, 16);
		MaxWidth = BitConverter.ToInt32(_header, 24);
		MaxHeight = BitConverter.ToInt32(_header, 28);
		GuestPid = BitConverter.ToInt32(_header, 44);
	}

	public long PublishCounter
	{
		get
		{
			_view.ReadArray(32, _header, 32, 8);
			return BitConverter.ToInt64(_header, 32);
		}
	}

	public int LatestSlot
	{
		get
		{
			_view.ReadArray(40, _header, 40, 4);
			return BitConverter.ToInt32(_header, 40);
		}
	}

	/// <summary>
	/// Read the newest complete slot into <paramref name="dest"/> (allocated here if null or the wrong
	/// size). Returns false when the newest slot is empty, being written, or torn.
	/// </summary>
	public bool TryRead(Frame dest)
	{
		if (!IsCompatible)
		{
			return false;
		}

		var slot = LatestSlot;
		if (slot < 0 || slot >= SlotCount)
		{
			Missed++;
			return false;
		}

		var desc = SlotDescBase + SlotDescBytes * slot;
		var seq1 = ReadLong(desc);
		if ((seq1 & 1L) != 0L)
		{
			Torn++;
			return false;
		}

		var width = ReadInt(desc + 24);
		var height = ReadInt(desc + 28);
		if (width <= 0 || height <= 0 || width > MaxWidth || height > MaxHeight)
		{
			return false;
		}

		var layerBytes = (long)width * height * 4;
		var needed = layerBytes * Layers;
		Ensure(dest, (int)layerBytes);
		var baseOffset = HeaderBytes + SlotStride * slot;
		ReadInto(dest.Colour, baseOffset, (int)layerBytes);
		ReadInto(dest.Depth, baseOffset + layerBytes, (int)layerBytes);
		ReadInto(dest.Overlay, baseOffset + 2 * layerBytes, (int)layerBytes);

		var seq2 = ReadLong(desc);
		if (seq1 != seq2)
		{
			Torn++;
			return false;
		}

		dest.Seq = seq1;
		dest.GuestFrame = ReadLong(desc + 8);
		dest.HostFrame = ReadLong(desc + 16);
		dest.Width = width;
		dest.Height = height;
		dest.Near = ReadFloat(desc + 32);
		dest.Far = ReadFloat(desc + 36);
		dest.Fov = ReadFloat(desc + 40);
		dest.Flags = (uint)ReadInt(desc + 44);
		dest.CamX = ReadDouble(desc + 48);
		dest.CamY = ReadDouble(desc + 56);
		dest.CamZ = ReadDouble(desc + 64);
		dest.Yaw = ReadFloat(desc + 72);
		dest.Pitch = ReadFloat(desc + 76);
		dest.Roll = ReadFloat(desc + 80);
		dest.FirstPerson = ReadInt(desc + 84) != 0;
		dest.CaptureNanos = ReadLong(desc + 88);
		dest.PublishNanos = ReadLong(desc + 96);
		Reads++;
		return true;
	}

	private static void Ensure(Frame dest, int layerBytes)
	{
		if (dest.Colour == null || dest.Colour.Length != layerBytes)
		{
			dest.Colour = new byte[layerBytes];
			dest.Depth = new byte[layerBytes];
			dest.Overlay = new byte[layerBytes];
		}
	}

	private void ReadInto(byte[] dst, long offset, int count) => _view.ReadArray(offset, dst, 0, count);

	private long ReadLong(long o)
	{
		_view.ReadArray(o, _header, 0, 8);
		return BitConverter.ToInt64(_header, 0);
	}

	private int ReadInt(long o)
	{
		_view.ReadArray(o, _header, 0, 4);
		return BitConverter.ToInt32(_header, 0);
	}

	private float ReadFloat(long o) => BitConverter.ToSingle(BitConverter.GetBytes(ReadInt(o)), 0);

	private double ReadDouble(long o)
	{
		_view.ReadArray(o, _header, 0, 8);
		return BitConverter.ToDouble(_header, 0);
	}

	public void Dispose()
	{
		_view?.Dispose();
		_mmf?.Dispose();
	}
}
