import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

def find_ax(data, byte_val):
    matches = []
    for i in range(len(data) - 2):
        if data[i] == 0x3D and data[i+1] == byte_val and data[i+2] == 0x00:
            matches.append(i)
    return matches

print("CMP AX, '<':", find_ax(data, 0x3C))
print("CMP AX, 'C':", find_ax(data, 0x43))
print("CMP AX, 'D':", find_ax(data, 0x44))
print("CMP AX, 'U':", find_ax(data, 0x55))
