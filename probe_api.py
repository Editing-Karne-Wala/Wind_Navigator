"""Try the Antigravity daemon's local HTTP API to list/retrieve conversations."""
import json
import urllib.request
import ssl

# From the daemon config we found:
# httpPort: 5830, httpsPort: 5829, csrfToken: be95c3af-dfed-487a-bab2-b8ffb20e9e8b

base_url = "http://localhost:5830"
csrf_token = "be95c3af-dfed-487a-bab2-b8ffb20e9e8b"
target_id = "f84283df-311b-445c-a6a7-d8ba76bdf13b"

# Common API patterns to try
endpoints = [
    "/",
    "/api",
    "/api/conversations",
    "/api/conversation",
    "/api/chat",
    "/api/chats", 
    "/conversations",
    "/conversation",
    f"/api/conversations/{target_id}",
    f"/conversation/{target_id}",
    "/health",
    "/status",
    "/api/status",
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for endpoint in endpoints:
    url = base_url + endpoint
    try:
        req = urllib.request.Request(url)
        req.add_header('X-CSRF-Token', csrf_token)
        req.add_header('Accept', 'application/json')
        
        response = urllib.request.urlopen(req, timeout=3)
        body = response.read().decode('utf-8', errors='replace')
        print(f"✅ {response.status} {endpoint}")
        if len(body) < 500:
            print(f"   Body: {body}")
        else:
            print(f"   Body ({len(body)} chars): {body[:300]}...")
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace') if e.fp else ''
        print(f"❌ {e.code} {endpoint}")
        if body and len(body) < 200:
            print(f"   Body: {body}")
    except Exception as e:
        print(f"⚠️  ERR {endpoint}: {type(e).__name__}: {e}")

# Also try the HTTPS port
print("\n\n=== Trying HTTPS port 5829 ===")
base_url = "https://localhost:5829"
for endpoint in ["/", "/api", "/api/conversations"]:
    url = base_url + endpoint
    try:
        req = urllib.request.Request(url)
        req.add_header('X-CSRF-Token', csrf_token)
        req.add_header('Accept', 'application/json')
        response = urllib.request.urlopen(req, timeout=3, context=ctx)
        body = response.read().decode('utf-8', errors='replace')
        print(f"✅ {response.status} {endpoint}")
        if len(body) < 500:
            print(f"   Body: {body}")
        else:
            print(f"   Body ({len(body)} chars): {body[:300]}...")
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace') if e.fp else ''
        print(f"❌ {e.code} {endpoint}")
        if body and len(body) < 200:
            print(f"   Body: {body}")
    except Exception as e:
        print(f"⚠️  ERR {endpoint}: {type(e).__name__}: {e}")
