import sys

def dump_sprite(exe_path, offset, width=16, height=16):
    with open(exe_path, 'rb') as f:
        f.seek(offset)
        data = f.read(width * height)
    
    for y in range(height):
        row = ""
        for x in range(width):
            b = data[y * width + x]
            if b == 196:
                row += "#"
            elif b == 0 or b == 255:
                row += "."
            else:
                row += str(b % 10)
        print(row)

dump_sprite('C:\\Users\\Dorp\\.gemini\\antigravity-ide\\scratch\\universal-modder\\PMAN.EXE', 36082)
print("---")
dump_sprite('C:\\Users\\Dorp\\.gemini\\antigravity-ide\\scratch\\universal-modder\\PMAN.EXE', 36563)
