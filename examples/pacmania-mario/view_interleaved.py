import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

def print_sprite_interleaved(block, offset):
    lines = []
    # 4 bytes per row. 16 rows.
    # Block is 64 bytes.
    # First 32 bytes are even rows (0, 2, 4, ..., 14)
    # Next 32 bytes are odd rows (1, 3, 5, ..., 15)
    for y in range(16):
        if y % 2 == 0:
            byte_offset = (y // 2) * 4
        else:
            byte_offset = 32 + (y // 2) * 4
        
        row_str = ""
        for x in range(4):
            b = block[byte_offset + x]
            for shift in (6, 4, 2, 0):
                px = (b >> shift) & 3
                if px == 0: row_str += " "
                elif px == 1: row_str += "." # Green
                elif px == 2: row_str += "x" # Red
                elif px == 3: row_str += "#" # Yellow
        lines.append(row_str)

    # Let's count yellows (#)
    w = sum([l.count('#') for l in lines])
    if w > 80: # Pacman has a lot of yellow
        print(f"Offset {offset}:")
        for l in lines:
            print(l)
        print("---")

for i in range(25000, len(data) - 64, 2):
    print_sprite_interleaved(data[i:i+64], i)
