import struct

with open('PMAN.EXE', 'rb') as f:
    f.seek(36082)
    cga_data = f.read(16384)

width = 320
height = 200

bmp_header = b'BM'
file_size = 14 + 40 + 4 * 4 + width * height
bmp_header += struct.pack('<I', file_size)
bmp_header += b'\x00\x00\x00\x00'
bmp_header += struct.pack('<I', 14 + 40 + 4 * 4)

dib_header = struct.pack('<I', 40)
dib_header += struct.pack('<I', width)
dib_header += struct.pack('<i', -height) # top-down
dib_header += struct.pack('<H', 1)
dib_header += struct.pack('<H', 8)
dib_header += struct.pack('<I', 0)
dib_header += struct.pack('<I', width * height)
dib_header += struct.pack('<I', 2835)
dib_header += struct.pack('<I', 2835)
dib_header += struct.pack('<I', 4)
dib_header += struct.pack('<I', 0)

palette = b'\x00\x00\x00\x00\x00\xff\x00\x00\x00\x00\xff\x00\x00\xff\xff\x00'

pixels = bytearray(width * height)
for y in range(height):
    # CGA memory is split: even lines at 0, odd lines at 8192
    if y % 2 == 0:
        offset = (y // 2) * 80
    else:
        offset = 8192 + (y // 2) * 80
        
    for x in range(80):
        if offset + x < len(cga_data):
            b = cga_data[offset + x]
            px_idx = y * width + x * 4
            pixels[px_idx] = (b >> 6) & 3
            pixels[px_idx+1] = (b >> 4) & 3
            pixels[px_idx+2] = (b >> 2) & 3
            pixels[px_idx+3] = (b >> 0) & 3

with open('SPRITESHEET.BMP', 'wb') as f:
    f.write(bmp_header + dib_header + palette + pixels)

print("Created SPRITESHEET.BMP")
