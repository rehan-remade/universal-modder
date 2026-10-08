import sys

with open('PMAN.EXE', 'rb') as f:
    data = bytearray(f.read())

# Revert MOV AL, 'M' -> MOV AL, 'C'
if data[6664 + 1] == 0x4D: data[6664 + 1] = 0x43

# Revert CMP AX, 'M' -> CMP AX, 'C'
for offset in [1980, 2608, 2796]:
    if data[offset + 1] == 0x4D: data[offset + 1] = 0x43

# Revert CMP AX, 'M' -> CMP AX, '<'
for offset in [1890, 2601, 2789]:
    if data[offset + 1] == 0x4D: data[offset + 1] = 0x3C

# Revert CMP AX, 'M' -> CMP AX, 'D'
for offset in [1954, 2613, 2801, 17241]:
    if data[offset + 1] == 0x4D: data[offset + 1] = 0x44

with open('PMAN.EXE', 'wb') as f:
    f.write(data)

print("Reverted assembly patches.")
