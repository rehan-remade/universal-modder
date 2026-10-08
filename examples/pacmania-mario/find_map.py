import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

# Map might be an array of strings. Look for a block with many '.' (2E) or '*' (2A) or spaces (20)
# Let's count '.' in 256-byte blocks
for i in range(0, len(data)-256, 128):
    block = data[i:i+256]
    if block.count(b'.') > 30:
        print(f"Possible map at {i}")
        # print ascii
        s = "".join([chr(b) if 32 <= b <= 126 else ' ' for b in block])
        print(s[:64])
