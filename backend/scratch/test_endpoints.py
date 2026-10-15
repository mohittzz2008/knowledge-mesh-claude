import urllib.request
import json

headers = {'X-Clerk-User-Id': 'test-user', 'Content-Type': 'application/json'}

try:
    req = urllib.request.Request('http://localhost:8000/api/v1/platforms', headers=headers)
    response = urllib.request.urlopen(req)
    data = json.loads(response.read())
    print("Platforms:")
    for p in data:
        print(f"- {p['key']}")
except Exception as e:
    print(f"Error fetching platforms: {e}")
