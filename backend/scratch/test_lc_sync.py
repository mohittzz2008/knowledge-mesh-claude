import urllib.request, urllib.error
try:
    req = urllib.request.Request(
        'http://localhost:8000/api/v1/platforms/leetcode/sync',
        method='POST',
        data=b'{"username":"demo_lc_user_test"}',
        headers={'Content-Type':'application/json', 'X-Clerk-User-Id': 'test-user-sync'}
    )
    resp = urllib.request.urlopen(req)
    print("LC AUTH:", resp.status, resp.read())
except urllib.error.HTTPError as e:
    print("LC ERROR:", e.code, e.read())
