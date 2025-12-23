import shutil
import uuid
from pathlib import Path
import importlib

import pytest


@pytest.fixture
def server_module(tmp_path):
    # Copy db.json to a temp location and patch server module to use it
    repo_dir = Path(__file__).parent
    orig_db = repo_dir / 'db.json'
    tmp_db = tmp_path / 'db.json'
    shutil.copy(orig_db, tmp_db)

    # Import and patch server module
    srv = importlib.import_module('server')
    srv.DATA_FILE = str(tmp_db)
    srv._db_cache = None
    srv._db_cache_mtime = None
    return srv


def test_load_db(server_module):
    db = server_module.load_db()
    assert isinstance(db, dict)
    assert 'households' in db and 'users' in db and 'events' in db


def test_user_lookup(server_module):
    db = server_module.load_db()
    user = server_module.get_user_by_token(db, '38d5da259f054945b6bd0e518e45f789')
    assert user is not None
    assert user['username'] == 'דניאל'
    assert server_module.get_user_by_token(db, 'invalid_token') is None


def test_household_lookup(server_module):
    db = server_module.load_db()
    h = server_module.get_household(db, '2cde7647014345179c935294b2704f74')
    assert h is not None
    assert h.get('dogName') is not None


def test_date_functions(server_module):
    import datetime
    today = server_module._start_of_today()
    assert isinstance(today, datetime.datetime)
    now_ts = int(datetime.datetime.now().timestamp())
    assert isinstance(server_module._event_date(now_ts), datetime.date)


def test_scoring_system(server_module):
    assert server_module.compute_points_for_event('poop') == 3
    assert server_module.compute_points_for_event('pee') == 2
    assert server_module.compute_points_for_event('walk') == 1
    assert server_module.compute_points_for_event('reward') == 1
    assert server_module.compute_points_for_event('accident') == -2


def test_scoreboard(server_module):
    db = server_module.load_db()
    scoreboard, family_total, family_weekly = server_module.compute_scoreboard(db, '2cde7647014345179c935294b2704f74')
    assert isinstance(scoreboard, list)
    assert isinstance(family_total, int)
    assert isinstance(family_weekly, int)


def test_today_events(server_module):
    db = server_module.load_db()
    today = server_module._start_of_today().date()
    # ensure it runs without errors
    events_today = [e for e in db['events'] if server_module._event_date(e['timestamp']) == today]
    assert isinstance(events_today, list)


def test_walk_types_in_scoreboard(server_module):
    import time
    now = int(time.time())
    household_id = 'hh_test'
    user_a = {'id': 'u_a', 'username': 'A', 'email': 'a@example.com', 'householdId': household_id}
    user_b = {'id': 'u_b', 'username': 'B', 'email': 'b@example.com', 'householdId': household_id}
    db = {
        'households': [{'id': household_id, 'dogName': 'שיצו'}],
        'users': [user_a, user_b],
        'events': [
            {'id': 'e1', 'householdId': household_id, 'type': 'walk_morning', 'timestamp': now, 'userId': 'u_a'},
            {'id': 'e2', 'householdId': household_id, 'type': 'walk_afternoon', 'timestamp': now, 'userId': 'u_b'},
            {'id': 'e3', 'householdId': household_id, 'type': 'walk_evening', 'timestamp': now, 'userId': 'u_a'},
            {'id': 'e4', 'householdId': household_id, 'type': 'poop', 'timestamp': now, 'userId': 'u_b'},
        ]
    }
    scoreboard, family_total, family_weekly = server_module.compute_scoreboard(db, household_id)
    assert family_total == 6


def test_api_simulation(server_module):
    # Ensure AppHandler is importable
    assert hasattr(server_module, 'AppHandler')