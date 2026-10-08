import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

def print_sprite_16x16(block, offset):
    lines = []
    for y in range(16):
        row_str = ""
        for x in range(4): # 4 bytes per row
            b = block[y * 4 + x]
            for shift in (6, 4, 2, 0):
                px = (b >> shift) & 3
                if px == 0: row_str += " "
                else: row_str += "#"
        lines.append(row_str)
    
    # check if it looks like a circle (middle rows wider than top/bottom)
    w = [len(l.strip()) for l in lines]
    if sum(w) > 100:
        print(f"Offset {offset}:")
        for l in lines:
            print(l)
        print("---")

for i in range(20000, len(data) - 64, 64):
    block = data[i:i+64]
    print_sprite_16x16(block, i)
