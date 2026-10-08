import sys

with open('SPRITESHEET.BMP', 'rb') as f:
    f.read(70) # Skip header
    pixels = f.read(64000)

width = 320
for y in range(176, 200, 16):
    print(f"Row {y}:")
    for row in range(y, y+16, 2):
        s = ""
        for x in range(0, 320, 4):
            px = pixels[row * width + x]
            if px == 0: s += " "
            elif px == 1: s += "G"
            elif px == 2: s += "R"
            elif px == 3: s += "Y"
        print(s)
    print("---")
