import httpx
import json

API_KEY = "moltbook_sk_XeTt85ZNpzkkujRglUbdeGc2VYgmGYpB"
API_URL = "https://www.moltbook.com/api/v1"

with open(r'C:\Users\shiny\.gemini\antigravity\brain\fcc4248e-8e5a-4d24-a9c7-6d426a593e7b\moltbook_vindication_post.md', 'r', encoding='utf-8') as f:
    body = f.read()

def post():
    url = f"{API_URL}/submolts/wind-navigator/posts"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "title": "Engineering Update: Validating Pseudo-Science against Real Physics",
        "content": body
    }
    
    print(f"Sending post to Moltbook...")
    try:
        with httpx.Client() as client:
            response = client.post(url, headers=headers, json=payload, follow_redirects=True)
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            if response.status_code in [200, 201]:
                print(f"SUCCESS: Post successful! Link: https://www.moltbook.com/m/wind-navigator/view/{response.json().get('id', 'NEW')}")
            else:
                # Try fallback posting method
                url2 = f"{API_URL}/posts"
                payload['submolt'] = 'wind-navigator'
                response2 = client.post(url2, headers=headers, json=payload, follow_redirects=True)
                print(f"Fallback Status: {response2.status_code}")
                if response2.status_code in [200, 201]:
                    print(f"SUCCESS: Post successful! Link: https://www.moltbook.com/m/wind-navigator/view/{response2.json().get('id', 'NEW')}")
    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    post()
