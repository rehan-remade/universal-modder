import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

def print_char(block):
    for b in block:
        print(f"{b:08b}".replace('0', ' ').replace('1', '#'))

# Let's search for FF FF FF FF in 8-byte blocks
for i in range(20000, len(data) - 8):
    block = data[i:i+8]
    if block.count(0xFF) >= 2 and block[0] in (0x0F, 0x1F, 0x3F, 0x7F, 0xF0, 0xF8, 0xFC, 0xFE):
        # Could be a corner of pacman!
        pass

# Let's just dump ALL 8x8 chars that have at least 2 lines of FF
matches = []
for i in range(20000, len(data) - 8, 8):
    block = data[i:i+8]
    if block.count(0xFF) >= 2:
        matches.append(i)

print(f"Found {len(matches)} potential font characters with dense pixels.")
for m in matches[:20]:
    print(f"Offset {m}:")
    print_char(data[m:m+8])

