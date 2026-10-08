import sys
import itertools

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

chars = [0x43, 0x3C, 0x5E, 0x76] # C, <, ^, v
chars2 = [0x43, 0x3C, 0x56, 0x5E] # C, <, V, ^

for perm in itertools.permutations(chars):
    pat = bytes(perm)
    idx = data.find(pat)
    if idx != -1:
        print(f"Found permutation {pat.hex()} at {idx}")

for perm in itertools.permutations(chars2):
    pat = bytes(perm)
    idx = data.find(pat)
    if idx != -1:
        print(f"Found permutation {pat.hex()} at {idx}")
        
# Check for null-separated or word-separated
