import re

file_path = r'C:\Users\shiny\Desktop\conversation.txt'

with open(file_path, 'rb') as f:
    data = f.read()

print(f"File size: {len(data)} bytes.")

# Extract all ASCII strings of length 10 or more
# This bypasses all encryption/encoding if the strings are plain text inside
ascii_strings = re.findall(b'[\\x20-\\x7e]{10,}', data)
print(f"Found {len(ascii_strings)} ASCII strings.")

# Extract all UTF-16 strings (like Antigravity exports)
utf16_strings = re.findall(b'([\\x20-\\x7e]\\x00){10,}', data)
print(f"Found {len(utf16_strings)} potential UTF-16 strings.")

# Search for the specific 'physics' keywords in the raw bytes
keywords = [b'quadrance', b'spread', b'classical', b'trigonometry', b'physics', b'benchmark', b'faster']
for kw in keywords:
    matches = [m.start() for m in re.finditer(kw, data, re.IGNORECASE)]
    if matches:
        print(f"Keyword '{kw.decode()}' found {len(matches)} times!")
        # Print the surrounding bytes (100 before, 200 after)
        start = max(0, matches[0] - 100)
        end = min(len(data), matches[0] + 300)
        context = data[start:end]
        # Clean up the output for display
        clean_context = "".join(chr(b) if 32 <= b <= 126 else "." for b in context)
        print(f"  Snippet: {clean_context}")

# Save all extracted strings to a new file for you to read
with open('extracted_strings.txt', 'w', encoding='utf-8') as f:
    for s in ascii_strings:
        try:
            f.write(s.decode('ascii') + '\n')
        except:
            pass
    print("All extracted strings saved to 'extracted_strings.txt'")
