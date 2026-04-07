"""
Extract readable text strings directly from binary file
using regex pattern matching for UTF-8 text sequences.
Also try to detect if the content is compressed.
"""
import re
import os
import gzip
import zlib

filepath = r'C:\Users\shiny\.gemini\antigravity\conversations\f84283df-311b-445c-a6a7-d8ba76bdf13b.pb'

with open(filepath, 'rb') as f:
    data = f.read()

print(f"File size: {len(data)} bytes")
print(f"First 32 bytes (hex): {data[:32].hex()}")
print(f"First 32 bytes (repr): {repr(data[:32])}")
print()

# Check for compression signatures
if data[:2] == b'\x1f\x8b':
    print("DETECTED: gzip compressed!")
    data = gzip.decompress(data)
    print(f"Decompressed size: {len(data)} bytes")
elif data[:4] == b'PK\x03\x04':
    print("DETECTED: ZIP format!")
else:
    # Try zlib decompress
    try:
        decompressed = zlib.decompress(data)
        print(f"DETECTED: zlib compressed! Decompressed size: {len(decompressed)} bytes")
        data = decompressed
    except:
        try:
            decompressed = zlib.decompress(data, -15)  # raw deflate
            print(f"DETECTED: raw deflate! Decompressed size: {len(decompressed)} bytes")
            data = decompressed
        except:
            print("No compression detected, working with raw data")

print()

# Method 1: Extract all printable ASCII strings of length >= 10
print("=" * 80)
print("METHOD 1: Extracting ASCII strings (length >= 10)")
print("=" * 80)

# Find sequences of printable ASCII characters
pattern = rb'[\x20-\x7e]{10,}'
matches = re.findall(pattern, data)
print(f"Found {len(matches)} strings")

# Filter for interesting strings (likely conversation content)
long_strings = []
short_strings = []
for m in matches:
    text = m.decode('ascii', errors='replace')
    if len(text) > 80:
        long_strings.append(text)
    elif len(text) > 15:
        short_strings.append(text)

print(f"  Long strings (>80 chars): {len(long_strings)}")
print(f"  Medium strings (15-80 chars): {len(short_strings)}")

# Write everything to output
output_path = r'C:\Users\shiny\.gemini\antigravity\playground\crystal-satellite\conversation_extracted.txt'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(f"Extracted from: {filepath}\n")
    f.write(f"File size: {len(data)} bytes\n")
    f.write(f"Total strings found: {len(matches)}\n")
    f.write("=" * 80 + "\n\n")
    
    f.write("LONG STRINGS (likely conversation messages):\n")
    f.write("=" * 80 + "\n\n")
    for i, s in enumerate(long_strings):
        f.write(f"\n--- String #{i+1} ({len(s)} chars) ---\n")
        f.write(s + "\n")
    
    f.write("\n\n" + "=" * 80 + "\n")
    f.write("MEDIUM STRINGS (metadata, labels, etc.):\n")
    f.write("=" * 80 + "\n\n")
    for i, s in enumerate(short_strings):
        f.write(f"  [{i+1}] {s}\n")

print(f"\nOutput written to: {output_path}")

# Print preview
print("\n" + "=" * 80)
print("PREVIEW OF LONG STRINGS:")
print("=" * 80)
for i, s in enumerate(long_strings[:20]):
    print(f"\n--- #{i+1} ({len(s)} chars) ---")
    print(s[:500])
    if len(s) > 500:
        print(f"  ... [{len(s)} total chars]")

print("\n" + "=" * 80)
print("PREVIEW OF MEDIUM STRINGS (first 50):")
print("=" * 80)
for i, s in enumerate(short_strings[:50]):
    print(f"  [{i+1}] {s}")
