import re, math
from collections import Counter

data = open(r'C:\Users\shiny\.gemini\antigravity\conversations\f84283df-311b-445c-a6a7-d8ba76bdf13b.pb', 'rb').read()

counts = Counter(data)
total = len(data)
entropy = -sum((c/total) * math.log2(c/total) for c in counts.values())
print(f'File size: {len(data)} bytes')
print(f'Shannon entropy: {entropy:.4f} bits/byte (max 8.0)')
print(f'Unique byte values: {len(counts)}/256')

strings = [m.decode('ascii') for m in re.findall(rb'[\x20-\x7e]{6,}', data)]
print(f'\nASCII strings (>=6 chars): {len(strings)}')
for s in strings:
    print(f'  "{s}"')
