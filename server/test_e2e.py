import time
import threading
import requests
import os
import json
import tempfile
import uuid
import signal

import pytest

from flask_server import app, load_db, save_db


@pytest.fixture(scope='module')
def start_flask_server():
    # Run Flask app in a background thread on a random available port
    port = 5001
    server_thread = threading.Thread(target=lambda: app.run(host='127.0.0.1', port=port, debug=False), daemon=True)
    server_thread.start()
    # Wait for server to start
    time.sleep(1)
    yield f'http://127.0.0.1:{port}'
    # Teardown: not much to do since daemon thread will exit on process end


def test_household_members_and_promote(start_flask_server):
    base = start_flask_server
    # Use existing token for דניאל from db.json
    db = load_db()
    admin_user = None
    for u in db['users']:
        if u.get('isAdmin') and u['householdId'] == '2cde7647014345179c935294b2704f74':
            admin_user = u
            break
    assert admin_user
    headers = {'Authorization': 'Bearer ' + admin_user['token']}

    # List members
    resp = requests.get(base + '/api/household/members', headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert 'members' in data
    members = data['members']
    assert any(m['username'] == 'דניאל' for m in members)

    # Pick a non-admin member and promote them
    non_admin = next((m for m in members if not m.get('isAdmin')), None)
    assert non_admin
    resp = requests.post(base + f"/api/household/members/{non_admin['id']}/manager",
                         headers=headers, json={'isAdmin': True})
    assert resp.status_code == 200
    j = resp.json()
    assert j.get('isAdmin') is True

    # Demote back
    resp = requests.post(base + f"/api/household/members/{non_admin['id']}/manager",
                         headers=headers, json={'isAdmin': False})
    assert resp.status_code == 200
    j = resp.json()
    assert j.get('isAdmin') is False