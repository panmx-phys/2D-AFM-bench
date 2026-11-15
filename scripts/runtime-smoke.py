"""Check a disposable source or packaged HTTP service without a GUI dependency."""
import json
import re
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def check(url):
    def get(path):
        with urlopen(url.rstrip('/') + path, timeout=30) as response:
            return response.read()

    html = get('/').decode()
    token = re.search(r'name="afm-token" content="([^"]+)"', html).group(1)
    assets = re.findall(r'(?:src|href)="(/[^\"]+)"', html)
    assert assets, 'No frontend assets declared'
    for path in assets:
        assert get(path), path

    def call(method, payload=None, authenticated=True):
        headers = {'Content-Type': 'application/json'}
        if authenticated:
            headers['X-AFM-Token'] = token
        request = Request(url.rstrip('/') + '/api/' + method,
                          json.dumps(payload or {}).encode(), headers)
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    try:
        call('bootstrap', authenticated=False)
        raise AssertionError('Unauthenticated API access succeeded')
    except HTTPError as exc:
        assert exc.code == 403
    session = call('demo')
    assert session['synthetic']
    scan_id = next(s['id'] for s in session['scans'] if s['channel'] == 'Z Height')
    raw = call('scan', {'id': scan_id, 'raw': True})
    operations = [{'type': 'plane', 'method': 'gwyddion'}]
    result = call('process', {'id': scan_id, 'operations': operations})
    assert result['operations'] == operations
    assert result['history'][-1]['model']['backend']['engine'] == 'Gwyddion C'
    assert call('scan', {'id': scan_id})['history'] == result['history']
    assert call('scan', {'id': scan_id, 'raw': True})['data'] == raw['data']
    undone = call('process', {'id': scan_id, 'operations': []})
    assert undone['data'] == raw['data'] and not undone['history']
    print(json.dumps({'passed': True, 'assets': assets, 'checks': [
        'HTTP authentication', 'synthetic session', 'native plane correction',
        'saved recipe replay', 'immutable raw pixels', 'undo']}, indent=2))


if __name__ == '__main__':
    check(sys.argv[1])
