import sys

with open('PMAN.EXE', 'rb') as f:
    data = bytearray(f.read())

# Patch MOV AL, 'C' -> MOV AL, 'M'
data[6664 + 1] = 0x4D

# Patch CMP AX, 'C' -> CMP AX, 'M'
for offset in [1980, 2608, 2796]:
    data[offset + 1] = 0x4D

# Patch CMP AX, '<' -> CMP AX, 'M'
for offset in [1890, 2601, 2789]:
    data[offset + 1] = 0x4D

# Patch CMP AX, 'D' -> CMP AX, 'M' (If D is down)
for offset in [1954, 2613, 2801, 17241]:
    data[offset + 1] = 0x4D

# Write back
with open('PMAN_MARIO.EXE', 'wb') as f:
    f.write(data)

print("Patched PMAN.EXE into PMAN_MARIO.EXE successfully.")
