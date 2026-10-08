import sys
import struct

def find_pacman(exe_path):
    with open(exe_path, 'rb') as f:
        data = f.read()

    print(f"File size: {len(data)}")
    
    # Heuristic for 8-bit linear VGA: A 16x16 block of bytes where many bytes are the same color (yellow, say 0x2c or 0x0e or 0x14)
    # Pacman circle:
    # ..xxxx..
    # .xxxxxx.
    # xxxxxxxx
    # xxxx....
    # xxxxxxxx
    # .xxxxxx.
    # ..xxxx..
    
    # Just look for sequences of identical bytes with some gaps
    for i in range(len(data) - 256):
        block = data[i:i+256]
        # Count most frequent byte (excluding 0 which is often background)
        freq = {}
        for b in block:
            if b != 0 and b != 255:
                freq[b] = freq.get(b, 0) + 1
        
        if freq:
            max_b = max(freq, key=freq.get)
            if freq[max_b] > 100 and freq[max_b] < 150: # A circle takes up about 120-150 pixels in a 16x16 grid
                print(f"Possible 8-bit VGA match at {i}: color={max_b}, count={freq[max_b]}")
                
find_pacman('C:\\Users\\Dorp\\.gemini\\antigravity-ide\\scratch\\universal-modder\\PMAN.EXE')
