import sys

def dump_hex(exe_path, offset, width=16, height=16):
    with open(exe_path, 'rb') as f:
        f.seek(offset)
        data = f.read(width * height)
    
    for y in range(height):
        row = ""
        for x in range(width):
            b = data[y * width + x]
            if b == 196:
                row += " ##"
            elif b == 0:
                row += " .."
            else:
                row += f" {b:02x}"
        print(row)

exe = 'PMAN.EXE'
offsets = [36082, 36563]
for o in offsets:
    print(f"Offset {o}:")
    dump_hex(exe, o)
    print("---")
