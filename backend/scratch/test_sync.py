import urllib.request, urllib.error
try:
    # Testing sync WITHOUT valid auth header
    req = urllib.request.Request(
        'http://localhost:8000/api/v1/platforms/github/sync',
        method='POST',
        data=b'{"username":"torvalds"}',
        headers={'Content-Type':'application/json'}
    )
    resp = urllib.request.urlopen(req)
    print("NO AUTH:", resp.status, resp.read())
except urllib.error.HTTPError as e:
    print("NO AUTH ERROR:", e.code, e.read())

try:
    # Testing sync WITH valid auth header (simulating X-Clerk-User-Id)
    req2 = urllib.request.Request(
        'http://localhost:8000/api/v1/platforms/github/sync',
        method='POST',
        data=b'{"username":"torvalds"}',
        headers={'Content-Type':'application/json', 'X-Clerk-User-Id': 'test-user-sync'}
    )
    resp2 = urllib.request.urlopen(req2)
    print("AUTH:", resp2.status, resp2.read())
except urllib.error.HTTPError as e:
    print("AUTH ERROR:", e.code, e.read())
