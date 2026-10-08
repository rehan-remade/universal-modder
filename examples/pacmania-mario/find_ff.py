import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

# Search for sequences of FFs
idx = -1
while True:
    idx = data.find(b'\xff\xff', idx + 1)
    if idx == -1: break
    # check if there is a pattern of FF FF
    # Let's just dump 32 bytes around it
    print(f"Offset {idx}: {data[idx-8:idx+24].hex()}")

