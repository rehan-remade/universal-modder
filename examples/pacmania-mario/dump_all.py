import sys

def dump_sprite(exe_path, offset, width=16, height=16):
    with open(exe_path, 'rb') as f:
        f.seek(offset)
        data = f.read(width * height)
    
    row_strings = []
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
        row_strings.append(row)
    return row_strings

exe = 'PMAN.EXE'
start = 36082
for i in range(10):
    offset = start + i * 256
    print(f"Offset {offset}:")
    for r in dump_sprite(exe, offset):
        print(r)
    print("---")
