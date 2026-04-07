"""Extract and analyze the chat.ChatSessionStore.index to find the missing conversation."""
import sqlite3
import json

db_path = r'C:\Users\shiny\AppData\Roaming\Antigravity\User\globalStorage\state.vscdb'
target = 'f84283df-311b-445c-a6a7-d8ba76bdf13b'

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get the chat session store index
c.execute("SELECT value FROM ItemTable WHERE key = 'chat.ChatSessionStore.index'")
row = c.fetchone()

if row:
    val = row[0]
    # It might be bytes or string
    if isinstance(val, bytes):
        val = val.decode('utf-8', errors='replace')
    
    print(f"Value length: {len(val)} chars")
    print(f"Value type: {type(val)}")
    
    # Write full value to file for inspection
    with open('chat_index.json', 'w', encoding='utf-8') as f:
        f.write(val)
    print("Full value written to chat_index.json")
    
    # Try to parse as JSON
    try:
        data = json.loads(val)
        print(f"\nParsed JSON type: {type(data)}")
        if isinstance(data, list):
            print(f"Number of entries: {len(data)}")
            # Check if target conversation is in the list
            found = False
            for entry in data:
                if isinstance(entry, dict):
                    entry_str = json.dumps(entry)
                    if target in entry_str:
                        print(f"\n*** FOUND TARGET CONVERSATION ***")
                        print(json.dumps(entry, indent=2)[:2000])
                        found = True
            if not found:
                print(f"\n*** TARGET '{target}' NOT FOUND IN INDEX ***")
                print("\nFirst 3 entries (sample):")
                for e in data[:3]:
                    print(json.dumps(e, indent=2)[:500])
        elif isinstance(data, dict):
            print(f"Keys: {list(data.keys())[:20]}")
            if target in str(data):
                print("*** TARGET FOUND IN DATA ***")
            else:
                print(f"*** TARGET NOT IN DATA ***")
            # Show structure
            for k, v in list(data.items())[:5]:
                print(f"\n  Key: {k}")
                print(f"  Value: {json.dumps(v)[:300]}")
    except json.JSONDecodeError as e:
        print(f"Not valid JSON: {e}")
        print(f"First 500 chars: {val[:500]}")
else:
    print("Key 'chat.ChatSessionStore.index' not found!")

conn.close()
