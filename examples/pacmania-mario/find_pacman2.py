import sys

def find_pacman_yellow(exe_path):
    with open(exe_path, 'rb') as f:
        data = f.read()
    
    matches = []
    # Pacman is yellow (color 14). Let's look for 16x16 blocks with a lot of 14s.
    for i in range(len(data) - 256):
        block = data[i:i+256]
        count_14 = block.count(14)
        if 80 <= count_14 <= 160:
            matches.append(i)
            
    # Filter overlapping matches
    filtered = []
    for m in matches:
        if not filtered or m > filtered[-1] + 250:
            filtered.append(m)
            
    print(f"Found {len(filtered)} possible sprites:")
    for m in filtered:
        print(f"Offset: {m}")
        # Dump it
        for y in range(16):
            row = ""
            for x in range(16):
                b = data[m + y * 16 + x]
                if b == 14:
                    row += "Y"
                elif b == 0:
                    row += "."
                else:
                    row += f"{b:02x}"
            print(row)
        print("---")

find_pacman_yellow('C:\\Users\\Dorp\\.gemini\\antigravity-ide\\scratch\\universal-modder\\PMAN.EXE')
