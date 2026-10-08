import sys

with open('PMAN.EXE', 'rb') as f:
    data = f.read()

# Search for INT 21h with AH=25, AL=1F
print("INT 21h AH=25h AL=1Fh:", data.find(b'\xb8\x1f\x25'))
print("INT 21h AH=25h AL=1Fh:", data.find(b'\xb4\x25\xb0\x1f'))
# Or direct write to 0000:007C
