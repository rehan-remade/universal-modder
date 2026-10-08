import sys

with open('sprites.txt', 'r') as f:
    lines = f.readlines()

for i in range(len(lines)):
    if lines[i].startswith("Offset "):
        sprite = lines[i+1:i+17]
        # Look for Pacman characteristics:
        # A circle is about 12-14 pixels wide, 12-14 pixels high
        # top and bottom rows should be empty or narrow
        # middle rows should be wide
        if len(sprite) == 16:
            w = [len(l.strip()) for l in sprite]
            if w[0] == 0 and w[15] == 0 and w[7] > 10 and w[8] > 10:
                print("Potential circle at", lines[i].strip())
                for l in sprite:
                    print(l.rstrip())
                print("---")
