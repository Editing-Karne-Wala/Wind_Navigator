"""Find the currently running Antigravity daemon and its active ports."""
import os
import json
import glob

# Check ALL daemon config files for the most recent one
daemon_dir = r'C:\Users\shiny\.gemini\antigravity\daemon'
configs = glob.glob(os.path.join(daemon_dir, '*.json'))

print("=== All daemon config files ===")
for cfg_path in sorted(configs, key=os.path.getmtime, reverse=True):
    mtime = os.path.getmtime(cfg_path)
    with open(cfg_path) as f:
        data = json.load(f)
    print(f"\n  File: {os.path.basename(cfg_path)}")
    print(f"  Modified: {mtime}")
    print(f"  Content: {json.dumps(data, indent=2)}")

# Also check if there's an active daemon by looking at recent log files
print("\n\n=== Most recent daemon logs ===")
logs = glob.glob(os.path.join(daemon_dir, '*.log'))
logs.sort(key=os.path.getmtime, reverse=True)
for log_path in logs[:3]:
    sz = os.path.getsize(log_path)
    mtime = os.path.getmtime(log_path)
    print(f"\n  {os.path.basename(log_path)} ({sz:,} bytes, mtime={mtime})")
    # Read last few lines
    with open(log_path, 'r', errors='replace') as f:
        lines = f.readlines()
        print(f"  Total lines: {len(lines)}")
        # Show last 10 lines
        for line in lines[-10:]:
            print(f"    {line.rstrip()}")
