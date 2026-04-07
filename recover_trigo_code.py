import codecs

file_path = r'C:\Users\shiny\Desktop\conversation.txt'
with codecs.open(file_path, 'r', 'utf-16-le') as f:
    text = f.read()

print(f"File size: {len(text)} characters.")
print("=== Search for Trigo Benchmarks ===")

# Search for key Rational Trigo terms
keywords = ['quadrance', 'spread', 'trigo', 'sin', 'cos', 'timeit', 'benchmark', 'faster']
found = []
for kw in keywords:
    if kw.lower() in text.lower():
        found.append(kw)

print(f"Keywords found: {', '.join(found)}")

# Extract any Python code blocks containing 'quadrance' or 'sin'
import re
code_blocks = re.findall(r'```python\n(.*?)\n```', text, re.DOTALL)
print(f"Found {len(code_blocks)} code blocks.")

for i, block in enumerate(code_blocks):
    if 'quadrance' in block or 'spread' in block or 'timeit' in block:
        print(f"\n--- Code Block {i+1} ---")
        print(block[:1000] + ("..." if len(block) > 1000 else ""))
