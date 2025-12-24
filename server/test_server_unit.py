import os
import tempfile
import json
import datetime
import server


def test_compute_points():
    assert server.compute_points_for_event('poop') == 3
    assert server.compute_points_for_event('pee') == 2
    assert server.compute_points_for_event('walk') == 1
    assert server.compute_points_for_event('walk_morning') == 1
    assert server.compute_points_for_event('feed_morning') == 1
    assert server.compute_points_for_event('accident') == -2


def test_event_date_and_start_of_today():
    today = server._start_of_today()
    assert isinstance(today, datetime.datetime)
    ts = int(datetime.datetime.now().timestamp())
    assert server._event_date(ts) == datetime.datetime.fromtimestamp(ts).date()


def test_get_user_and_household_lookup():
    db = {
        'households': [{'id': 'hh1', 'dogName': 'Buddy'}],
        'users': [{'id': 'u1', 'username': 'alice', 'token': 't1', 'householdId': 'hh1'}],
        'events': []
    }
    assert server.get_user_by_token(db, 't1')['username'] == 'alice'
    assert server.get_user_by_token(db, 'nope') is None
    assert server.get_household(db, 'hh1')['dogName'] == 'Buddy'
    assert server.get_household(db, 'x') is None


def test_compute_scoreboard_simple():
    now = int(datetime.datetime.now().timestamp())
    hh = 'hh-test'
    u1 = {'id': 'u1', 'username': 'A', 'householdId': hh}
    u2 = {'id': 'u2', 'username': 'B', 'householdId': hh}
    db = {
        'households': [{'id': hh, 'dogName': 'Rex'}],
        'users': [u1, u2],
        'events': [
            {'id': 'e1', 'householdId': hh, 'type': 'poop', 'timestamp': now, 'userId': 'u1'},
            {'id': 'e2', 'householdId': hh, 'type': 'pee', 'timestamp': now, 'userId': 'u2'},
            {'id': 'e3', 'householdId': hh, 'type': 'walk_morning', 'timestamp': now, 'userId': 'u1'},
        ]
    }
    scoreboard, family_total, family_weekly = server.compute_scoreboard(db, hh)
    # u1: poop(3) + walk(1) = 4, u2: pee(2)
    assert family_total == 6
    assert any(s['username'] == 'A' and s['totalPoints'] == 4 for s in scoreboard)
    assert any(s['username'] == 'B' and s['totalPoints'] == 2 for s in scoreboard)


def test_save_and_load_db_roundtrip(tmp_path, monkeypatch):
    temp_db = tmp_path / 'db.json'
    data = {'households': [], 'users': [], 'events': []}
    with open(temp_db, 'w', encoding='utf-8') as fh:
        json.dump(data, fh)
    # monkeypatch DATA_FILE to point to temp file
    monkeypatch.setattr(server, 'DATA_FILE', str(temp_db))
    loaded = server.load_db()
    assert isinstance(loaded, dict)
    # modify and save
    loaded['users'].append({'id': 'u1', 'username': 'x'})
    server.save_db(loaded)
    # reload and check
    reloaded = server.load_db()
    assert any(u['username'] == 'x' for u in reloaded['users'])
