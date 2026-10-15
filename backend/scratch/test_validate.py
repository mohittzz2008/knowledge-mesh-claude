import urllib.request, json
try:
    req = urllib.request.Request('http://localhost:8000/api/v1/platforms/github/validate', method='POST', data=b'{"username":"torvalds"}', headers={'Content-Type':'application/json'})
    print('GH:', json.loads(urllib.request.urlopen(req).read()))
    
    req2 = urllib.request.Request('http://localhost:8000/api/v1/platforms/hackerrank/validate', method='POST', data=b'{"username":"shashank"}', headers={'Content-Type':'application/json'})
    print('HR:', json.loads(urllib.request.urlopen(req2).read()))
except Exception as e:
    print('ERROR:', e)
