import time
import threading
import requests
import uuid
import tempfile
import os
import json

from flask_server import app, load_db, save_db


def start_flask_in_thread(port=5002):
    t = threading.Thread(target=lambda: app.run(host='127.0.0.1', port=port, debug=False), daemon=True)
    t.start()
    time.sleep(1)
    return f'http://127.0.0.1:{port}'


def test_register_login_and_today_flow(tmp_path):
    base = start_flask_in_thread(5002)
    # Use a temp copy of db.json for isolation
    db_path = os.path.join(os.path.dirname(__file__), 'db.json')
    with open(db_path, 'r', encoding='utf-8') as fh:
        orig = json.load(fh)
    tmpdb = tmp_path / 'db.json'
    with open(tmpdb, 'w', encoding='utf-8') as fh:
        json.dump(orig, fh, ensure_ascii=False, indent=2)

    # Monkeypatch flask_server's data file by setting environment var before load
    os.environ['TEST_DB_FILE'] = str(tmpdb)

    # Register a new user (creates a household)
    email = f'testuser+{uuid.uuid4().hex}@example.com'
    resp = requests.post(base + '/api/register', json={'email': email, 'password': 'p', 'username': 'Tester'})
    assert resp.status_code == 200
    data = resp.json()
    token = data['token']

    # record a generic walk event and confirm normalization
    headers = {'Authorization': 'Bearer ' + token}
    resp = requests.post(base + '/api/events', headers=headers, json={'type': 'walk'})
    assert resp.status_code == 200
    j = resp.json()
    assert j.get('success') is True

    # call today and ensure hasWalkMorning/afternoon/evening appears (at least one flag)
    resp = requests.get(base + '/api/today', headers=headers)
    assert resp.status_code == 200
    td = resp.json()
    schedule = td.get('schedule') or {}
    assert any(schedule.get(k) for k in ('hasWalkMorning', 'hasWalkAfternoon', 'hasWalkEvening', 'hasWalk'))
