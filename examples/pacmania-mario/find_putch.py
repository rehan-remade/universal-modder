import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

# Search for MOV AX, 'C'
# B8 43 00
def find_mov_ax(data, char_byte):
    matches = []
    for i in range(len(data) - 2):
        if data[i] == 0xB8 and data[i+1] == char_byte and data[i+2] == 0x00:
            matches.append(i)
    return matches

print("MOV AX, 'C':", find_mov_ax(data, 0x43))
print("MOV AX, '<':", find_mov_ax(data, 0x3C))
print("MOV AX, 'V':", find_mov_ax(data, 0x56))
print("MOV AX, '^':", find_mov_ax(data, 0x5E))

# Let's also check for pushes: 68 43 00 (PUSH 'C')
def find_push(data, char_byte):
    matches = []
    for i in range(len(data) - 2):
        if data[i] == 0x68 and data[i+1] == char_byte and data[i+2] == 0x00:
            matches.append(i)
    return matches

print("PUSH 'C':", find_push(data, 0x43))
print("PUSH '<':", find_push(data, 0x3C))

# Also what about AL?
