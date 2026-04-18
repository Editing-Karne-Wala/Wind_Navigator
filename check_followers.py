import httpx
import json
import sys

# Set output to utf-8
sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "moltbook_sk_XeTt85ZNpzkkujRglUbdeGc2VYgmGYpB"
API_URL = "https://www.moltbook.com/api/v1"

def get_followers():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    try:
        with httpx.Client() as client:
            # Step 1: Get my profile
            me_res = client.get(f"{API_URL}/agents/me", headers=headers)
            me_data = me_res.json()
            my_id = me_data.get('id')
            print(f"Agent ID: {my_id} ({me_data.get('username')})")
            
            # Step 2: Get followers for that ID
            # Trying several possible endpoints
            endpoints = [
                f"{API_URL}/agents/{my_id}/followers",
                f"{API_URL}/followers/me",
                f"{API_URL}/agents/me/followers"
            ]
            
            for url in endpoints:
                res = client.get(url, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    followers = data.get('followers', data.get('items', []))
                    if followers:
                        print("FOLLOWERS_START")
                        for f in followers:
                            # Safely get username/name
                            name = f.get('username', f.get('name', 'Unknown'))
                            print(f"- {name}")
                        print("FOLLOWERS_END")
                        return
            print("No followers found or endpoint mismatch.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_followers()
