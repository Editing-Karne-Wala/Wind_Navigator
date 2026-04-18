import sys

def check_pb(filepath):
    with open(filepath, 'rb') as f:
        header = f.read(4)
        print(f"Header (hex): {header.hex().upper()}")
        if header.startswith(b'PK\x03\x04'):
            print("This file looks like a ZIP archive.")
        elif header.startswith(b'\x1f\x8b'):
            print("This file looks like a GZIP compressed file.")
        elif b'SQLite' in header:
            print("This file looks like a SQLite database.")
        
        f.seek(0)
        data = f.read()
        
        keywords = [b'Rational', b'Trigonometry', b'Physics', b'Simulation']
        for kw in keywords:
            for enc in ['utf-8', 'utf-16-le', 'utf-16-be']:
                try:
                    search_term = kw.decode('utf-8').encode(enc)
                    idx = data.find(search_term)
                    if idx != -1:
                        print(f"Found '{kw.decode('utf-8')}' ({enc}) at offset {idx}")
                except:
                    pass

if __name__ == "__main__":
    check_pb(sys.argv[1])
