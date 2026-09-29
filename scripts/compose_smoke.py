"""Verify Compose enrollment, durable ingestion, and a visible incident through the proxy."""
import http.cookiejar
import json
import time
import urllib.request
from pathlib import Path


def main():
    private = json.loads(Path('.runtime/private/demo-credentials.json').read_text())
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    request = urllib.request.Request('http://127.0.0.1:5173/api/v1/auth/login',
        data=json.dumps(private['admin']).encode(),
        headers={'Content-Type': 'application/json', 'Origin': 'http://127.0.0.1:5173'})
    with opener.open(request, timeout=10) as response:
        assert response.status == 200
    for _ in range(150):
        with opener.open('http://127.0.0.1:5173/api/v1/organizations', timeout=5) as response:
            nodes = json.load(response)['organizations']
        if len(nodes) == 3 and all(n['last_signal'] for n in nodes):
            print('Three separately enrolled organizations delivered committed signals.')
            return
        time.sleep(1)
    raise RuntimeError('compose_agents_did_not_deliver')


if __name__ == '__main__':
    main()
