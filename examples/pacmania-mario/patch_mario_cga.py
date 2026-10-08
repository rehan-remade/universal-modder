import sys

with open('PMAN.EXE', 'rb') as f:
    data = bytearray(f.read())

cga_start = 36082

mario = [
    [0,0,0,0,2,2,2,2,2,0,0,0,0,0,0,0],
    [0,0,0,2,2,2,2,2,2,2,2,2,0,0,0,0],
    [0,0,0,0,3,3,3,0,3,3,0,0,0,0,0,0],
    [0,0,0,3,3,3,0,3,3,3,3,0,0,0,0,0],
    [0,0,0,3,3,3,0,3,3,0,0,0,0,0,0,0],
    [0,0,0,3,3,3,3,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,3,3,3,3,3,3,3,0,0,0,0,0],
    [0,0,0,0,0,1,1,2,1,1,0,0,0,0,0,0],
    [0,0,0,0,1,1,2,1,2,1,1,0,0,0,0,0],
    [0,0,0,1,1,1,1,1,1,1,1,1,0,0,0,0],
    [0,0,0,1,1,0,1,1,1,0,1,1,0,0,0,0],
    [0,0,0,0,0,0,1,1,1,0,0,0,0,0,0,0],
    [0,0,0,3,3,0,0,0,0,0,3,3,0,0,0,0],
    [0,0,3,3,3,0,0,0,0,0,3,3,3,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
]

def get_pixel(data, x, y):
    if y % 2 == 0:
        offset = cga_start + (y // 2) * 80 + (x // 4)
    else:
        offset = cga_start + 8192 + (y // 2) * 80 + (x // 4)
    if offset >= len(data): return 0
    b = data[offset]
    shift = 6 - 2 * (x % 4)
    return (b >> shift) & 3

def set_pixel(data, x, y, color):
    if y % 2 == 0:
        offset = cga_start + (y // 2) * 80 + (x // 4)
    else:
        offset = cga_start + 8192 + (y // 2) * 80 + (x // 4)
    if offset >= len(data): return
    b = data[offset]
    shift = 6 - 2 * (x % 4)
    mask = ~(3 << shift)
    b = (b & mask) | (color << shift)
    data[offset] = b

replaced = 0
# ONLY check rows 176 and 192 (where Pacman sprites are stored)
for cell_y in [176, 192]:
    for cell_x in range(0, 320, 16):
        yellow_count = 0
        green_count = 0
        red_count = 0
        for y in range(16):
            for x in range(16):
                px = get_pixel(data, cell_x + x, cell_y + y)
                if px == 3: yellow_count += 1
                if px == 1: green_count += 1
                if px == 2: red_count += 1
                
        # If it's a Pacman sprite (very yellow)
        if yellow_count > 40:
            print(f"Found Pacman at {cell_x}, {cell_y} (yellows: {yellow_count})")
            for y in range(16):
                for x in range(16):
                    set_pixel(data, cell_x + x, cell_y + y, mario[y][x])
            replaced += 1

with open('PMAN.EXE', 'wb') as f:
    f.write(data)

print(f"Replaced {replaced} Pacman sprites perfectly!")
