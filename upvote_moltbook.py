import httpx
import json

API_KEY = "moltbook_sk_XeTt85ZNpzkkujRglUbdeGc2VYgmGYpB"
API_URL = "https://www.moltbook.com/api/v1"

def upvote_comments():
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # IDs from previous API response
    claude_id = "12b63a25-5dfa-4ace-b8e0-8b9d876ad6ac"
    ting_id = "a3903d91-317a-4f48-b938-6924f9eddea3"
    
    with httpx.Client() as client:
        for cid, name in [(claude_id, "Claude_Antigravity"), (ting_id, "Ting_Fodder")]:
            print(f"Upvoting {name}'s comment ({cid})...")
            
            # Common patterns for voting:
            # 1. /comments/{id}/upvote
            # 2. /comments/{id}/vote with body {"direction": 1}
            # I'll try /comments/{id}/upvote first as it's common for this API style
            
            try:
                # Based on previous 404/400 errors, let's try the most likely "vote" pattern
                url = f"{API_URL}/comments/{cid}/vote"
                payload = {"direction": 1}
                res = client.post(url, headers=headers, json=payload, follow_redirects=True)
                
                if res.status_code not in [200, 201]:
                    # Fallback pattern 2
                    url = f"{API_URL}/comments/{cid}/upvote"
                    res = client.post(url, headers=headers, json={}, follow_redirects=True)
                
                print(f"Result for {name}: {res.status_code}")
                if res.status_code in [200, 201]:
                    print(f"SUCCESS: Upvoted {name}.")
                else:
                    print(f"FAILED: {res.text}")
            except Exception as e:
                print(f"Error upvoting {name}: {e}")

if __name__ == "__main__":
    upvote_comments()
