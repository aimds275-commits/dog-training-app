import threading
import time
import requests
import os
import json
import uuid
from flask_server import app, load_db, save_db


def start_flask(port=5010):
    t = threading.Thread(target=lambda: app.run(host='127.0.0.1', port=port, debug=False), daemon=True)
    t.start()
    time.sleep(1)
    return f'http://127.0.0.1:{port}'


def test_invite_endpoints_admin_and_errors(tmp_path):
    # use isolated DB copy and set TEST_DB_FILE before starting server
    db_path = os.path.join(os.path.dirname(__file__), 'db.json')
    with open(db_path, 'r', encoding='utf-8') as fh:
        orig = json.load(fh)
    tmpdb = tmp_path / 'db.json'
    with open(tmpdb, 'w', encoding='utf-8') as fh:
        json.dump(orig, fh, ensure_ascii=False, indent=2)
    os.environ['TEST_DB_FILE'] = str(tmpdb)
    base = start_flask(5010)

    # find an admin user in the copied DB
    db = load_db()
    admin = next((u for u in db['users'] if u.get('isAdmin')), None)
    assert admin, 'No admin user found in test db'
    admin_headers = {'Authorization': 'Bearer ' + admin['token']}

    # create a new invite (admin should succeed)
    resp = requests.post(base + '/api/invite', headers=admin_headers)
    assert resp.status_code == 200
    j = resp.json()
    assert 'inviteTokens' in j

    # reset invites (admin)
    resp = requests.post(base + '/api/invite/reset', headers=admin_headers)
    assert resp.status_code == 200
    j = resp.json()
    assert 'inviteTokens' in j

    # missing token should be 401
    resp = requests.post(base + '/api/invite')
    assert resp.status_code == 401

    # non-admin should be 403 — register a new user using the household invite token
    household = next((h for h in db['households'] if h['id'] == admin['householdId']), None)
    assert household and household.get('inviteTokens'), 'No invite token on admin household'
    invite_token = household['inviteTokens'][0]
    email = f'tmp+{uuid.uuid4().hex}@example.com'
    resp = requests.post(base + '/api/register', json={'email': email, 'password': 'p', 'username': 'tmpuser', 'inviteToken': invite_token})
    assert resp.status_code == 200
    token = resp.json()['token']
    headers = {'Authorization': 'Bearer ' + token}
    # non-admin try to create invite -> should be forbidden
    resp = requests.post(base + '/api/invite', headers=headers)
    assert resp.status_code == 403
