import sys

with open('SPRITESHEET.BMP', 'rb') as f:
    f.read(70) # Skip header
    pixels = f.read(64000)

cga_data = bytearray(16384)
width = 320
height = 200

for y in range(height):
    if y % 2 == 0:
        offset = (y // 2) * 80
    else:
        offset = 8192 + (y // 2) * 80
        
    for x in range(80):
        px_idx = y * width + x * 4
        p0 = pixels[px_idx]
        p1 = pixels[px_idx+1]
        p2 = pixels[px_idx+2]
        p3 = pixels[px_idx+3]
        
        b = (p0 << 6) | (p1 << 4) | (p2 << 2) | p3
        if offset + x < 16384:
            cga_data[offset + x] = b

with open('PMAN.EXE', 'rb') as f:
    exe_data = bytearray(f.read())

# Overwrite corrupted spritesheet
exe_data[36082:36082+16384] = cga_data

with open('PMAN.EXE', 'wb') as f:
    f.write(exe_data)

print("Restored original spritesheet!")
