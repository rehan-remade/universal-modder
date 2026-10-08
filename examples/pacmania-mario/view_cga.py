import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

def print_sprite_16x16(block):
    for y in range(16):
        row_str = ""
        for x in range(4): # 4 bytes per row
            b = block[y * 4 + x]
            for shift in (6, 4, 2, 0):
                px = (b >> shift) & 3
                if px == 0: row_str += " "
                elif px == 1: row_str += "."
                elif px == 2: row_str += "x"
                elif px == 3: row_str += "#"
        print(row_str)
    print("---")

def search_pacman():
    matches = []
    # Search for blocks of 64 bytes where there are enough # (color 3)
    # Pacman circle is around 120-150 pixels of color 3. 
    # That means around 120-150 '3's in the 256 pixels.
    # We can count the number of 11s.
    for i in range(25000, len(data) - 64):
        block = data[i:i+64]
        c3_count = 0
        c0_count = 0
        for b in block:
            for shift in (6,4,2,0):
                if ((b >> shift) & 3) == 3: c3_count += 1
                if ((b >> shift) & 3) == 0: c0_count += 1
        
        if 80 <= c3_count <= 180 and c0_count > 50:
            # Let's check for a rough circle shape
            # Corners should be 0
            b_topleft = block[0]
            b_topright = block[3]
            b_botleft = block[15*4]
            b_botright = block[15*4+3]
            if b_topleft == 0 and b_botleft == 0:
                matches.append(i)

    # Filter overlapping
    filtered = []
    for m in matches:
        if not filtered or m > filtered[-1] + 60:
            filtered.append(m)
            
    print(f"Found {len(filtered)} possible sprites")
    for m in filtered[:15]:
        print(f"Offset {m}:")
        print_sprite_16x16(data[m:m+64])

search_pacman()
