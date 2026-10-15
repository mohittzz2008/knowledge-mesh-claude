import urllib.request, urllib.error
try:
    req = urllib.request.Request('http://localhost:8000/api/v1/platforms/github/validate', method='POST', data=b'{"username":"torvalds"}', headers={'Content-Type':'application/json'})
    resp = urllib.request.urlopen(req)
    print(resp.status, resp.read())
except urllib.error.HTTPError as e:
    print(e.code, e.read())
