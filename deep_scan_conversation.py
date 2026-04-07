import codecs
import base64
import re
import json

file_path = r'C:\Users\shiny\Desktop\conversation.txt'

def analyze_file():
    print(f"--- Analyzing: {file_path} ---")
    
    # Try reading as UTF-16 first (as detected before)
    try:
        with codecs.open(file_path, 'r', 'utf-16-le') as f:
            data = f.read()
    except Exception as e:
        print(f"Error reading UTF-16: {e}")
        # Try raw binary if UTF-16 fails
        with open(file_path, 'rb') as f:
            data = f.read().decode('ascii', errors='ignore')

    print(f"Loaded {len(data)} characters.")

    # 1. Look for Base64 blobs
    # Base64 is usually A-Za-z0-9+/ with padding =
    b64_pattern = r'[A-Za-z0-9+/]{50,}=*' 
    potential_b64 = re.findall(b64_pattern, data)
    print(f"Found {len(potential_b64)} potential Base64 blocks.")

    # 2. Try to decode the largest B64 block
    if potential_b64:
        largest = max(potential_b64, key=len)
        print(f"Largest B64 block length: {len(largest)}")
        try:
            decoded = base64.b64decode(largest).decode('utf-8', errors='ignore')
            print("\n--- Decoded Preview (First 500 chars) ---")
            print(decoded[:500])
            
            # Search for 'rational' or 'quadrance' in decoded text
            if 'rational' in decoded.lower() or 'quadrance' in decoded.lower():
                print("\n[SUCCESS] Found Rational Trigo terms in Base64 block!")
        except:
            print("Failed to decode largest B64 block.")

    # 3. Look for JSON structures
    json_pattern = r'\{.*\}'
    potential_json = re.findall(json_pattern, data)
    print(f"Found {len(potential_json)} potential JSON objects.")

    # 4. Search for physics keywords globally
    keywords = ['quadrance', 'spread', 'classical', 'trigonometry', 'physics', 'engine', 'benchmark']
    for kw in keywords:
        indices = [m.start() for m in re.finditer(kw, data, re.IGNORECASE)]
        if indices:
            print(f"Keyword '{kw}' found {len(indices)} times (First at index {indices[0]})")
            # Print context
            start = max(0, indices[0] - 50)
            end = min(len(data), indices[0] + 150)
            print(f"  Context: ...{data[start:end]}...")

analyze_file()
