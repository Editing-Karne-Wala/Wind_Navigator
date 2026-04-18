import re

def find_sentences(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()
    
    # Try different encodings
    for encoding in ['utf-8', 'utf-16', 'utf-16-le', 'utf-16-be']:
        try:
            text = content.decode(encoding, errors='ignore')
            # Look for things that look like sentences
            matches = re.findall(r'[A-Z][a-z0-0 \-_,\.\?\!]{10,}', text)
            if matches:
                print(f"--- Encoding: {encoding} ---")
                for m in matches[:20]: # just first 20
                    print(m)
        except Exception:
            pass

if __name__ == "__main__":
    import sys
    find_sentences(sys.argv[1])
