"""Find all state/db/json files in Antigravity app data, excluding workspace storage."""
import os

roaming = r'C:\Users\shiny\AppData\Roaming\Antigravity'
gemini = r'C:\Users\shiny\.gemini\antigravity'

targets = ['.db', '.vscdb', '.json', '.sqlite', '.sqlite3', '.idx', '.index']

print("=== ROAMING APPDATA (non-workspace) ===")
for root, dirs, files in os.walk(roaming):
    if 'workspaceStorage' in root:
        continue
    for f in files:
        if any(f.endswith(ext) for ext in targets):
            fp = os.path.join(root, f)
            sz = os.path.getsize(fp)
            print(f"  {fp}  ({sz:,} bytes)")

print("\n=== GEMINI APPDATA (non-conversations, non-daemon, non-implicit) ===")
skip = ['conversations', 'daemon', 'implicit', 'node_modules', 'playground', 'browser_recordings']
for root, dirs, files in os.walk(gemini):
    if any(s in root for s in skip):
        continue
    for f in files:
        if any(f.endswith(ext) for ext in targets + ['.pb', '.txt']):
            fp = os.path.join(root, f)
            sz = os.path.getsize(fp)
            print(f"  {fp}  ({sz:,} bytes)")

# Also check the globalState vscdb which is likely the conversation index
print("\n=== GLOBAL STATE DB (likely conversation index) ===")
global_state = os.path.join(roaming, 'User', 'globalStorage', 'state.vscdb')
if os.path.exists(global_state):
    print(f"  Found: {global_state} ({os.path.getsize(global_state):,} bytes)")
else:
    # Search for it
    for root, dirs, files in os.walk(roaming):
        for f in files:
            if f == 'state.vscdb' and 'workspaceStorage' not in root:
                fp = os.path.join(root, f)
                print(f"  Found: {fp} ({os.path.getsize(fp):,} bytes)")
