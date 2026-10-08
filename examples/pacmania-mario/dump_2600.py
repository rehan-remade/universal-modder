import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

# Let's dump 64 bytes around 2600
start = 2580
print("Disassembly context:")
for i in range(start, start+100, 16):
    print(f"{i:04x}: {data[i:i+16].hex()}")

# Let's also search for 'U' (55 00)
print("'U' count:", data.count(b'\x55\x00'))
