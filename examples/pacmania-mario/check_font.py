import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

int10_count = data.count(b'\xcd\x10')
print(f"Found {int10_count} INT 10h calls.")

# Check for INT 21h
int21_count = data.count(b'\xcd\x21')
print(f"Found {int21_count} INT 21h calls.")

# Look for B8 12 00 (MOV AX, 0012h - set VGA 640x480)
# Or B8 13 00 (MOV AX, 0013h - set VGA 320x200 256 colors)
if b'\xb8\x13\x00' in data:
    print("Found MOV AX, 13h (Mode 13h)")

# BGA / CGA / text mode
