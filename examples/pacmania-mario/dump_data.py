import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

# Assuming data segment starts around 25000 (just a guess, file is 53K)
# Let's print out readable ascii in chunks of 64
for i in range(25000, 30000, 64):
    chunk = data[i:i+64]
    # replace non-ascii with '.'
    s = "".join([chr(b) if 32 <= b <= 126 else '.' for b in chunk])
    if any(c != '.' for c in s):
        print(f"{i:05d}: {s}")
