import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

# Search for 16x16 BGI image header (width-1=15, height-1=15) -> 0F 00 0F 00
# Or maybe width=16, height=16 -> 10 00 10 00
import struct

print("Searching for 0F 00 0F 00")
for i in range(len(data)-4):
    if data[i:i+4] == b'\x0f\x00\x0f\x00':
        print(f"Match at {i}")

print("Searching for 10 00 10 00")
for i in range(len(data)-4):
    if data[i:i+4] == b'\x10\x00\x10\x00':
        print(f"Match at {i}")
        
# CGA BGI putimage?
# In CGA 4-color mode, 2 bits per pixel. 16x16 is 4 bytes per row * 16 = 64 bytes.
