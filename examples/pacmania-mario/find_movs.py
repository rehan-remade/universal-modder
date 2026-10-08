import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

# B0 43 = MOV AL, 'C'
# B0 3C = MOV AL, '<'
# B0 56 = MOV AL, 'V'
# B0 5E = MOV AL, '^'
# C6 06 xx xx 43 = MOV byte ptr [xxxx], 'C'
# C6 46 xx 43 = MOV byte ptr [bp+xx], 'C'

def search_mov_al(data, char_byte):
    matches = []
    # MOV AL, char
    for i in range(len(data) - 1):
        if data[i] == 0xB0 and data[i+1] == char_byte:
            matches.append(i)
    return matches

print("MOV AL, 'C':", search_mov_al(data, 0x43))
print("MOV AL, '<':", search_mov_al(data, 0x3C))
print("MOV AL, 'V':", search_mov_al(data, 0x56))
print("MOV AL, '^':", search_mov_al(data, 0x5E))

# Also search for C6 06 ...
def search_mov_mem(data, char_byte):
    matches = []
    for i in range(len(data) - 4):
        if data[i] == 0xC6 and data[i+1] == 0x06 and data[i+4] == char_byte:
            matches.append(i)
    return matches

print("MOV [mem], 'C':", search_mov_mem(data, 0x43))
print("MOV [mem], '<':", search_mov_mem(data, 0x3C))
