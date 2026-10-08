import sys

def find_pacman_shape(exe_path):
    with open(exe_path, 'rb') as f:
        data = f.read()
    
    # Let's count non-zero pixels in each 16x16 block
    matches = []
    for i in range(len(data) - 256):
        block = data[i:i+256]
        # Pacman has roughly 120-150 non-transparent pixels. Let's assume 0 is transparent.
        non_zero_count = sum(1 for b in block if b != 0 and b != 255)
        
        # Let's see if we have a circle shape
        # Center pixels should be non-zero, corners should be zero
        
        corners_zero = (
            block[0] == 0 and block[15] == 0 and
            block[15*16] == 0 and block[15*16+15] == 0
        )
        
        center_non_zero = (
            block[7*16+7] != 0 and block[7*16+8] != 0 and
            block[8*16+7] != 0 and block[8*16+8] != 0
        )
        
        if 100 <= non_zero_count <= 180 and corners_zero and center_non_zero:
            matches.append(i)

    # Filter overlapping matches
    filtered = []
    for m in matches:
        if not filtered or m > filtered[-1] + 250:
            filtered.append(m)
            
    for m in filtered[:10]:
        print(f"Offset: {m}")
        for y in range(16):
            row = ""
            for x in range(16):
                b = data[m + y * 16 + x]
                if b == 0 or b == 255:
                    row += "."
                else:
                    row += "#"
            print(row)
        print("---")

find_pacman_shape('C:\\Users\\Dorp\\.gemini\\antigravity-ide\\scratch\\universal-modder\\PMAN.EXE')
