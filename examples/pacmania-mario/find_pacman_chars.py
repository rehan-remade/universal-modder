import sys
import struct

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

# Look for text-mode character+attribute combinations (Yellow = 0x0E)
# 43 0E = 'C' yellow
patterns = {
    "Yellow 'C'": b'\x43\x0e',
    "Yellow 'c'": b'\x63\x0e',
    "Yellow '<'": b'\x3c\x0e',
    "Yellow 'O'": b'\x4f\x0e',
    "Yellow 'V'": b'\x56\x0e',
    "Yellow '^'": b'\x5e\x0e',
    "Yellow ')'": b'\x29\x0e',
    "Yellow '('": b'\x28\x0e',
    "Yellow '@'": b'\x40\x0e'
}

for name, pat in patterns.items():
    count = data.count(pat)
    if count > 0:
        print(f"Found {count} occurrences of {name} ({pat.hex()})")

# Look for array of directions. Usually they are clustered together.
# Let's search for 'C' (43) close to '<' (3C) or similar
matches = []
for i in range(len(data) - 10):
    chunk = data[i:i+10]
    if b'\x43' in chunk and b'\x3c' in chunk:
        matches.append(i)

if matches:
    print(f"Found 'C' and '<' close to each other at {len(matches)} locations.")
    for m in matches[:5]:
        print(f"Offset {m}: {data[m:m+16].hex()}")

