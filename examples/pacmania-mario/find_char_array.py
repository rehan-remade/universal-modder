import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

# Search for MOV AL/DL/CL, 'C'
# AL: B0 43, DL: B2 43, CL: B1 43
# Let's search for 'C' (43), '<' (3C), 'V' (56), 'O' (4F), 'c' (63), 'v' (76), '^' (5E) in data segment

print("Dumping all printable ASCII strings of length >= 1 that have combinations of C, O, <, etc.")
# No, let's just dump the data segment from 36000 onwards and look for standalone characters
# Actually, let's look for assignments or byte arrays.
matches = []
for i in range(len(data) - 4):
    chunk = data[i:i+4]
    # If chunk has exactly characters like C, <, v, ^, O
    chars = set(chunk)
    valid = {b'C'[0], b'<'[0], b'O'[0], b'c'[0], b'>'[0], b'^'[0], b'v'[0], b'V'[0], b'o'[0], b')'[0], b'('[0]}
    if chars.issubset(valid):
        print(f"Found interesting chunk at {i}: {chunk}")

