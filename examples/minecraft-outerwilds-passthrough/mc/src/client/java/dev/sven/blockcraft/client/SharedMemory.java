package dev.sven.blockcraft.client;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.SymbolLookup;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.nio.charset.StandardCharsets;

/**
 * POSIX shared memory for the frame export: {@code shm_open} + {@code ftruncate} + {@code mmap}.
 *
 * <p>Written for this bridge instead of the GTA V example's Win32 {@code CreateFileMapping}, because
 * the two processes are not both Windows here: Minecraft runs as a native Linux JVM and Outer Wilds
 * runs as a Windows build under Proton. A POSIX shm object is a plain file at
 * {@code /dev/shm/<name>}, which the Wine process opens through {@code Z:\dev\shm\<name>} and maps
 * with an ordinary file mapping. Verified on this machine 2026-10-19 (see the project MODLOG).
 *
 * <p>Both sides use {@code <name>} without the leading slash; the JVM adds it, the host spells the
 * {@code Z:} path out.
 */
final class SharedMemory {
	private static final int O_CREAT = 0x40;
	private static final int O_RDWR = 0x02;
	private static final int S_IRUSR = 0x100;
	private static final int S_IWUSR = 0x80;
	private static final int PROT_READ = 0x1;
	private static final int PROT_WRITE = 0x2;
	private static final int MAP_SHARED = 0x01;

	final MemorySegment segment;

	private SharedMemory(final MemorySegment segment) {
		this.segment = segment;
	}

	/**
	 * Create (or open) {@code /dev/shm/<name>} at {@code size} bytes and map the whole of it.
	 *
	 * <p>{@code shm_unlink} is deliberately not called: the host may still be mapping the object from
	 * the previous run, and a fresh mapping of the same name is what lets a restarted guest be picked
	 * up without the host reconnecting. The object is small and the kernel reclaims it on reboot.
	 */
	static SharedMemory create(final String name, final long size) throws Throwable {
		Linker linker = Linker.nativeLinker();
		SymbolLookup libc = SymbolLookup.libraryLookup("libc.so.6", Arena.global());
		MethodHandle shmOpen = linker.downcallHandle(
			libc.find("shm_open").orElseThrow(),
			FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.JAVA_INT)
		);
		MethodHandle ftruncate = linker.downcallHandle(
			libc.find("ftruncate").orElseThrow(),
			FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.JAVA_INT, ValueLayout.JAVA_LONG)
		);
		MethodHandle mmap = linker.downcallHandle(
			libc.find("mmap").orElseThrow(),
			FunctionDescriptor.of(ValueLayout.ADDRESS, ValueLayout.ADDRESS, ValueLayout.JAVA_LONG,
				ValueLayout.JAVA_INT, ValueLayout.JAVA_INT, ValueLayout.JAVA_INT, ValueLayout.JAVA_LONG)
		);

		MemorySegment cName = Arena.global().allocateFrom(ValueLayout.JAVA_BYTE,
			("/" + name + "\0").getBytes(StandardCharsets.UTF_8));
		int fd = (int) shmOpen.invoke(cName, O_CREAT | O_RDWR, S_IRUSR | S_IWUSR);
		if (fd < 0) {
			throw new IllegalStateException("shm_open /" + name + " failed (errno " + fd + ")");
		}

		if ((int) ftruncate.invoke(fd, size) != 0) {
			throw new IllegalStateException("ftruncate /" + name + " to " + size + " failed");
		}

		MemorySegment map = (MemorySegment) mmap.invoke(
			MemorySegment.NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0L);
		if (map.address() == -1L) {
			throw new IllegalStateException("mmap /" + name + " failed");
		}

		return new SharedMemory(map.reinterpret(size));
	}
}
