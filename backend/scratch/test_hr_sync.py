import urllib.request, urllib.error
try:
    req2 = urllib.request.Request(
        'http://localhost:8000/api/v1/platforms/hackerrank/sync',
        method='POST',
        data=b'{"username":"shashank"}',
        headers={'Content-Type':'application/json', 'X-Clerk-User-Id': 'test-user-sync'}
    )
    resp2 = urllib.request.urlopen(req2)
    print("HR AUTH:", resp2.status, resp2.read())
except urllib.error.HTTPError as e:
    print("HR AUTH ERROR:", e.code, e.read())
