import sys

def search_cga(data):
    # A circle in 2bpp (color 3 = 11 binary).
    # Row 0: .. .. 11 11 11 11 11 11 .. ..
    # Let's search for some patterns.
    # Solid line of 16 pixels color 3 is FF FF.
    # Color 1 is 55 55. Color 2 is AA AA.
    # Let's look for a block of ~64 bytes with many FF, AA, or 55.
    
    matches = []
    for i in range(len(data) - 64):
        block = data[i:i+64]
        # count FF
        if block.count(b'\xff') > 10:
            matches.append(i)
    return matches

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

m = search_cga(data)
print(f"Found {len(m)} matches for CGA solid blocks")
