import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

start = 6640
print("Disassembly context around 6664:")
for i in range(start, start+64, 16):
    print(f"{i:04x}: {data[i:i+16].hex()}")

