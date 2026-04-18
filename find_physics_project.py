"""Recover terminal history and recently opened paths from state.vscdb."""
import sqlite3
import json

db_path = r'C:\Users\shiny\AppData\Roaming\Antigravity\User\globalStorage\state.vscdb'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 1. Get Terminal Command History
print("=== Terminal History Search ===")
c.execute("SELECT value FROM ItemTable WHERE key = 'terminal.history.entries.commands'")
row = c.fetchone()
if row:
    data = json.loads(row[0])
    entries = data.get('entries', [])
    print(f"Found {len(entries)} terminal commands.")
    for e in entries:
        cmd = e.get('key', '')
        if any(term in cmd.lower() for term in ['physics', 'trigo', 'rational', 'sim', 'engine', 'math', 'calc']):
            print(f"  [COMMAND]: {cmd}")

# 2. Get Recently Opened Folders
print("\n=== Recently Opened Paths ===")
c.execute("SELECT value FROM ItemTable WHERE key = 'history.recentlyOpenedPathsList'")
row = c.fetchone()
if row:
    data = json.loads(row[0])
    entries = data.get('entries', [])
    for e in entries:
        path = e.get('folderUri') or e.get('fileUri')
        if path:
            print(f"  [PATH]: {path}")

# 3. Check for any environment/workspace related keys
print("\n=== Workspace References ===")
c.execute("SELECT key, value FROM ItemTable WHERE key LIKE 'workspaces.%' OR key LIKE 'lastActiveWorkspace%'")
for k, v in c.fetchall():
    print(f"  {k}: {v[:200]}...")

conn.close()
