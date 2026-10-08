import sys
import struct

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

width = 320
height = len(data) // (width // 4)
if height == 0: height = 1

# BMP Header
bmp_header = b'BM'
file_size = 14 + 40 + 4 * 4 + width * height
bmp_header += struct.pack('<I', file_size)
bmp_header += b'\x00\x00\x00\x00'
bmp_header += struct.pack('<I', 14 + 40 + 4 * 4)

# DIB Header
dib_header = struct.pack('<I', 40)
dib_header += struct.pack('<I', width)
dib_header += struct.pack('<i', -height) # top-down
dib_header += struct.pack('<H', 1)
dib_header += struct.pack('<H', 8) # 8bpp
dib_header += struct.pack('<I', 0)
dib_header += struct.pack('<I', width * height)
dib_header += struct.pack('<I', 2835)
dib_header += struct.pack('<I', 2835)
dib_header += struct.pack('<I', 4)
dib_header += struct.pack('<I', 0)

# Palette (BGRA)
palette = b''
palette += b'\x00\x00\x00\x00' # Black
palette += b'\x00\xff\x00\x00' # Green
palette += b'\x00\x00\xff\x00' # Red
palette += b'\x00\xff\xff\x00' # Yellow

# Pixels
pixels = bytearray()
for i in range(len(data)):
    b = data[i]
    pixels.append((b >> 6) & 3)
    pixels.append((b >> 4) & 3)
    pixels.append((b >> 2) & 3)
    pixels.append((b >> 0) & 3)

with open('CGA.BMP', 'wb') as f:
    f.write(bmp_header)
    f.write(dib_header)
    f.write(palette)
    f.write(pixels)

print("Created CGA.BMP")
