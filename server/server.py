#!/usr/bin/env python3
"""
Simple backend server for the potty training app.

This server provides a very lightweight API layer over a JSON file used as
persistent storage. It also serves the static files for the client app
located in the sibling ``client`` directory. There is no external
dependency: everything is handled via Python's built‑in HTTP
infrastructure. This means the app can run in a constrained environment
without access to external package repositories.

All data is stored in a single JSON file (db.json) with the following
structure:

    {
        "households": [
            {
                "id": "...",
                "dogName": "...",
                "inviteTokens": ["..."]
            },
            ...
        ],
        "users": [
            {
                "id": "...",
                "username": "...",
                "password": "...",  # stored in plain text for simplicity
                "householdId": "...",
                "token": "..."
            },
            ...
        ],
        "events": [
            {
                "id": "...",
                "householdId": "...",
                "type": "feed_morning|feed_evening|walk|pee|poop|reward",
                "timestamp": 1700000000,
                "userId": "..."
            },
            ...
        ]
    }

Endpoints:

POST /api/register
    Body: {"username": str, "password": str, "inviteToken": optional str}
    Creates a new user. If inviteToken is provided and valid, the user will
    join the corresponding household. Otherwise a new household is created
    and a new invite token is generated for it. Returns a token which
    should be stored client‑side to authenticate future calls.

POST /api/login
    Body: {"username": str, "password": str}
    Logs an existing user in and returns their token.

GET /api/user
    Header: Authorization: Bearer <token>
    Returns basic user data (username, householdId), the household's dog
    name, invite tokens and the scoreboard for the household.

POST /api/dog
    Body: {"dogName": str}
    Header: Authorization: Bearer <token>
    Updates the household's dog name.

POST /api/events
    Body: {"type": str}
    Header: Authorization: Bearer <token>
    Records a new event (feed/walk/pee/poop/reward) and updates points
    accordingly.

POST /api/invite
    Header: Authorization: Bearer <token>
    Generates and returns a new invite token for the user's household.

GET /api/scores
    Header: Authorization: Bearer <token>
    Returns the household scoreboard sorted descending by points and the
    total family score.

Static files:
    Any request that does not begin with /api/ is served from the
    ``client`` directory relative to this file. When a directory is
    requested (e.g. ``/`` or ``/index.html``), the ``index.html`` file is
    returned.

Run this server with:
    python3 server.py

By default it binds to port 8000. You can override this by setting the
PORT environment variable.
"""

import json
import os
import uuid
import datetime
import logging
import sys
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('server.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), 'db.json')
CLIENT_DIR = os.path.join(os.path.dirname(__file__), '..', 'client')

# Database cache to avoid reading from disk on every request
_db_cache = None
_db_cache_mtime = None

def load_db():
    """Load the database from disk with caching. Creates an empty db if necessary."""
    global _db_cache, _db_cache_mtime
    
    # Check if file exists
    if not os.path.exists(DATA_FILE):
        logger.warning(f"Database file not found at {DATA_FILE}, creating new")
        _db_cache = {'households': [], 'users': [], 'events': []}
        _db_cache_mtime = None
        return _db_cache
    
    # Check if cache is still valid
    current_mtime = os.path.getmtime(DATA_FILE)
    if _db_cache is not None and _db_cache_mtime == current_mtime:
        # Cache hit - return cached version
        return _db_cache
    
    # Cache miss - load from disk
    with open(DATA_FILE, 'r', encoding='utf-8') as fh:
        try:
            _db_cache = json.load(fh)
            _db_cache_mtime = current_mtime
            logger.debug(f"Database loaded from disk: {len(_db_cache.get('households', []))} households, {len(_db_cache.get('users', []))} users, {len(_db_cache.get('events', []))} events")
            return _db_cache
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse database JSON: {e}")
            _db_cache = {'households': [], 'users': [], 'events': []}
            _db_cache_mtime = None
            return _db_cache


def save_db(db):
    """Persist the database to disk and update cache."""
    global _db_cache, _db_cache_mtime
    try:
        tmp_file = DATA_FILE + '.tmp'
        with open(tmp_file, 'w', encoding='utf-8') as fh:
            json.dump(db, fh, indent=2, ensure_ascii=False)
        os.replace(tmp_file, DATA_FILE)
        # Update cache
        _db_cache = db
        _db_cache_mtime = os.path.getmtime(DATA_FILE)
        logger.debug("Database saved successfully")
    except Exception as e:
        logger.error(f"Failed to save database: {e}")
        # Invalidate cache on error
        _db_cache = None
        _db_cache_mtime = None


def get_user_by_token(db, token):
    """Return the user dict matching the given token, or None."""
    for u in db['users']:
        if u.get('token') == token:
            return u
    return None


def get_household(db, household_id):
    for h in db['households']:
        if h['id'] == household_id:
            return h
    return None


def _start_of_today():
    """Return a datetime for the start of the current day (local time)."""
    now = datetime.datetime.now()
    return datetime.datetime(year=now.year, month=now.month, day=now.day)


def compute_points_for_event(event_type):
    """Define a simple point system for each event type."""
    return {
        'feed_morning': 1,
        'feed_evening': 1,
        'walk': 1,
        'pee': 2,
        'poop': 3,
        'reward': 1,
        'accident': -2,
    }.get(event_type, 0)


def _event_date(ts):
    return datetime.datetime.fromtimestamp(ts).date()


def compute_scoreboard(db, household_id):
    """Compute rich per-user stats and family totals for a household.

    - Per-user: total points, weekly points (last 7 days), streak (consecutive
      days with at least one scored event), and raw event counters.
    - Family: total and weekly total (sum of members).

    To avoid double-scoring, we deduplicate by (user, event_type, date): only
    the first occurrence of a given type for that user per day yields points.
    """
    today = _start_of_today().date()
    week_ago = today - datetime.timedelta(days=6)

    # index users in this household
    users = [u for u in db['users'] if u['householdId'] == household_id]
    user_index = {u['id']: u for u in users}

    # Prepare accumulators
    per_user = {
        u['id']: {
            'totalPoints': 0,
            'weeklyPoints': 0,
            'eventsByDay': {},  # date -> list of events
            'rawCounts': {},  # event_type -> count
        }
        for u in users
    }

    seen_for_points = set()  # (userId, event_type, date)

    for event in db['events']:
        if event['householdId'] != household_id:
            continue
        user_id = event.get('userId')
        if user_id not in per_user:
            continue
        date = _event_date(event['timestamp'])
        evt_type = event['type']

        # accumulate raw counts and history
        info = per_user[user_id]
        info['rawCounts'][evt_type] = info['rawCounts'].get(evt_type, 0) + 1
        info['eventsByDay'].setdefault(date, []).append(event)

        # de-duplicate for scoring
        key = (user_id, evt_type, date)
        if key in seen_for_points:
            continue
        seen_for_points.add(key)

        pts = compute_points_for_event(evt_type)
        if pts == 0:
            continue
        info['totalPoints'] += pts
        if week_ago <= date <= today:
            info['weeklyPoints'] += pts

    # compute streaks
    for user_id, info in per_user.items():
        streak = 0
        day = today
        while True:
            if day in info['eventsByDay']:
                streak += 1
                day = day - datetime.timedelta(days=1)
            else:
                break
        info['streak'] = streak

    # Build scoreboard list
    scoreboard = []
    for user_id, info in per_user.items():
        user = user_index[user_id]
        scoreboard.append({
            'userId': user_id,
            'username': user.get('username') or user.get('email'),
            'email': user.get('email'),
            'points': info['totalPoints'],
            'totalPoints': info['totalPoints'],
            'weeklyPoints': info['weeklyPoints'],
            'streak': info.get('streak', 0)
        })

    scoreboard.sort(key=lambda x: (-x['totalPoints'], x['username'] or ''))
    family_total = sum(p['totalPoints'] for p in scoreboard)
    family_weekly_total = sum(p['weeklyPoints'] for p in scoreboard)
    return scoreboard, family_total, family_weekly_total


class AppHandler(SimpleHTTPRequestHandler):
    """Custom handler that routes API calls and serves the client app."""

    def do_OPTIONS(self):
        # Handle CORS preflight requests
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def _send_json(self, data, status=200):
        try:
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionAbortedError, BrokenPipeError) as e:
            logger.warning(f"Client disconnected before response could be sent: {e}")
        except Exception as e:
            logger.error(f"Error sending JSON response: {e}")

    def _get_auth_token(self):
        # token may be provided as Bearer header or query param
        token = None
        auth_header = self.headers.get('Authorization')
        if auth_header and auth_header.lower().startswith('bearer '):
            token = auth_header.split(' ', 1)[1].strip()
        else:
            # fallback to query parameter for GET requests
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if 'token' in query:
                token = query['token'][0]
        return token

    def _read_json(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if not content_length:
            return None
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw.decode('utf-8'))
        except Exception:
            return None

    def _handle_api(self):
        parsed = urlparse(self.path)
        path = parsed.path
        # Only log important operations, not every GET request
        if self.command != 'GET' or path not in ['/api/today', '/api/history', '/api/scores']:
            logger.info(f"API Request: {self.command} {path}")
        db = load_db()
        # Register
        if path == '/api/register' and self.command == 'POST':
            data = self._read_json()
            logger.info(f"POST /api/register - New registration attempt")
            if not data or not data.get('email') or not data.get('password'):
                logger.warning("Registration failed: missing email or password")
                return self._send_json({'error': 'email and password required'}, 400)
            email = data['email'].strip().lower()
            display_name = (data.get('username') or '').strip()
            password = data['password']
            invite_token = data.get('inviteToken')
            logger.info(f"Registering user: {email}, invite: {bool(invite_token)}")
            # Check if email already exists
            if any(u.get('email', '').lower() == email for u in db['users']):
                return self._send_json({'error': 'email already exists'}, 400)
            # Determine household
            household_id = None
            if invite_token:
                # find household by invite token
                for h in db['households']:
                    if invite_token in h.get('inviteTokens', []):
                        household_id = h['id']
                        break
                if household_id is None:
                    return self._send_json({'error': 'invalid invite token'}, 400)
            # create household if not provided (first user becomes admin)
            if not household_id:
                household_id = uuid.uuid4().hex
                # default dog name empty
                new_invite = uuid.uuid4().hex
                db['households'].append({
                    'id': household_id,
                    'dogName': '',
                    'inviteTokens': [new_invite],
                    'dogAgeMonths': 0,
                    'dogPhotoUrl': ''
                })
            # create user
            user_id = uuid.uuid4().hex
            token = uuid.uuid4().hex
            db['users'].append({
                'id': user_id,
                'username': display_name or email.split('@')[0],
                'email': email,
                'password': password,
                'householdId': household_id,
                'token': token,
                'isAdmin': not invite_token  # creator without invite is admin
            })
            save_db(db)
            h = get_household(db, household_id)
            scoreboard, family_total, family_weekly_total = compute_scoreboard(db, household_id)
            return self._send_json({
                'token': token,
                'userId': user_id,
                'username': display_name or email.split('@')[0],
                'householdId': household_id,
                'dogName': h['dogName'],
                'dogAgeMonths': h.get('dogAgeMonths'),
                'dogPhotoUrl': h.get('dogPhotoUrl'),
                'inviteTokens': h.get('inviteTokens', []),
                'scoreboard': scoreboard,
                'familyTotal': family_total,
                'familyWeeklyTotal': family_weekly_total
            }, 200)
        # Login
        if path == '/api/login' and self.command == 'POST':
            data = self._read_json()
            logger.info(f"POST /api/login - Login attempt")
            if not data or not data.get('email') or not data.get('password'):
                logger.warning("Login failed: missing credentials")
                return self._send_json({'error': 'email and password required'}, 400)
            email = data['email'].strip().lower()
            password = data['password']
            logger.info(f"Login attempt for: {email}")
            for u in db['users']:
                # support both legacy username and new email login
                if (
                    (u.get('email', '').lower() == email or u.get('username') == email)
                    and u['password'] == password
                ):
                    # return token and household info
                    logger.info(f"Login successful: {u['username']} (household: {u['householdId']})")
                    h = get_household(db, u['householdId'])
                    scoreboard, family_total, family_weekly_total = compute_scoreboard(db, u['householdId'])
                    return self._send_json({
                        'token': u['token'],
                        'userId': u['id'],
                        'username': u['username'],
                        'householdId': u['householdId'],
                        'dogName': h['dogName'],
                        'dogAgeMonths': h.get('dogAgeMonths'),
                        'dogPhotoUrl': h.get('dogPhotoUrl'),
                        'inviteTokens': h.get('inviteTokens', []),
                        'scoreboard': scoreboard,
                        'familyTotal': family_total,
                        'familyWeeklyTotal': family_weekly_total,
                        'isAdmin': u.get('isAdmin', False)
                    }, 200)
            logger.warning(f"Login failed: invalid credentials for {email}")
            return self._send_json({'error': 'invalid credentials'}, 401)
        # Fetch user info
        if path == '/api/user' and self.command == 'GET':
            token = self._get_auth_token()
            if not token:
                return self._send_json({'error': 'missing token'}, 401)
            user = get_user_by_token(db, token)
            if not user:
                return self._send_json({'error': 'invalid token'}, 401)
            h = get_household(db, user['householdId'])
            scoreboard, family_total, family_weekly_total = compute_scoreboard(db, user['householdId'])
            return self._send_json({
                'userId': user['id'],
                'username': user['username'],
                'email': user.get('email'),
                'householdId': user['householdId'],
                'dogName': h['dogName'],
                'dogAgeMonths': h.get('dogAgeMonths'),
                'dogPhotoUrl': h.get('dogPhotoUrl'),
                'inviteTokens': h.get('inviteTokens', []),
                'scoreboard': scoreboard,
                'familyTotal': family_total,
                'familyWeeklyTotal': family_weekly_total,
                'isAdmin': user.get('isAdmin', False)
            }, 200)
        # Update dog name
        if path == '/api/dog' and self.command == 'POST':
            token = self._get_auth_token()
            if not token:
                return self._send_json({'error': 'missing token'}, 401)
            user = get_user_by_token(db, token)
            if not user:
                return self._send_json({'error': 'invalid token'}, 401)
            data = self._read_json()
            if not data or not data.get('dogName'):
                return self._send_json({'error': 'dogName required'}, 400)
            dog_name = data['dogName']
            h = get_household(db, user['householdId'])
            h['dogName'] = dog_name
            # optional extra profile fields
            if 'dogAgeMonths' in data:
                h['dogAgeMonths'] = data['dogAgeMonths']
            if 'dogPhotoUrl' in data:
                h['dogPhotoUrl'] = data['dogPhotoUrl']
            save_db(db)
            scoreboard, family_total, family_weekly_total = compute_scoreboard(db, user['householdId'])
            return self._send_json({
                'success': True,
                'dogName': dog_name,
                'dogAgeMonths': h.get('dogAgeMonths'),
                'dogPhotoUrl': h.get('dogPhotoUrl'),
                'scoreboard': scoreboard,
                'familyTotal': family_total,
                'familyWeeklyTotal': family_weekly_total
            }, 200)
        # Record event
        if path == '/api/events' and self.command == 'POST':
            token = self._get_auth_token()
            if not token:
                logger.warning("POST /api/events - Missing token")
                return self._send_json({'error': 'missing token'}, 401)
            user = get_user_by_token(db, token)
            if not user:
                logger.warning("POST /api/events - Invalid token")
                return self._send_json({'error': 'invalid token'}, 401)
            data = self._read_json()
            if not data or not data.get('type'):
                logger.warning(f"POST /api/events - Missing event type (user: {user['username']})")
                return self._send_json({'error': 'type required'}, 400)
            event_type = data['type']
            event_id = uuid.uuid4().hex
            timestamp = int(datetime.datetime.now(datetime.UTC).timestamp())
            logger.info(f"POST /api/events - User {user['username']} added event: {event_type}")
            db['events'].append({
                'id': event_id,
                'householdId': user['householdId'],
                'type': event_type,
                'timestamp': timestamp,
                'userId': user['id']
            })
            save_db(db)
            scoreboard, family_total, family_weekly_total = compute_scoreboard(db, user['householdId'])
            logger.info(f"Event recorded: {event_type}, new family total: {family_total}")
            return self._send_json({
                'success': True,
                'eventId': event_id,
                'scoreboard': scoreboard,
                'familyTotal': family_total,
                'familyWeeklyTotal': family_weekly_total
            }, 200)
        # Create invite token
        if path == '/api/invite' and self.command == 'POST':
            token = self._get_auth_token()
            if not token:
                return self._send_json({'error': 'missing token'}, 401)
            user = get_user_by_token(db, token)
            if not user:
                return self._send_json({'error': 'invalid token'}, 401)
            if not user.get('isAdmin'):
                return self._send_json({'error': 'only admin can manage invites'}, 403)
            h = get_household(db, user['householdId'])
            new_token = uuid.uuid4().hex
            h.setdefault('inviteTokens', []).append(new_token)
            save_db(db)
            return self._send_json({
                'inviteToken': new_token,
                'inviteTokens': h['inviteTokens']
            }, 200)
        # Reset invite tokens (revoke all and generate a single new link)
        if path == '/api/invite/reset' and self.command == 'POST':
            token = self._get_auth_token()
            if not token:
                return self._send_json({'error': 'missing token'}, 401)
            user = get_user_by_token(db, token)
            if not user:
                return self._send_json({'error': 'invalid token'}, 401)
            if not user.get('isAdmin'):
                return self._send_json({'error': 'only admin can reset invites'}, 403)
            h = get_household(db, user['householdId'])
            new_token = uuid.uuid4().hex
            h['inviteTokens'] = [new_token]
            save_db(db)
            return self._send_json({
                'inviteToken': new_token,
                'inviteTokens': h['inviteTokens']
            }, 200)
        # Fetch scoreboard only
        if path == '/api/scores' and self.command == 'GET':
            token = self._get_auth_token()
            if not token:
                return self._send_json({'error': 'missing token'}, 401)
            user = get_user_by_token(db, token)
            if not user:
                return self._send_json({'error': 'invalid token'}, 401)
            scoreboard, family_total, family_weekly_total = compute_scoreboard(db, user['householdId'])
            return self._send_json({
                'scoreboard': scoreboard,
                'familyTotal': family_total,
                'familyWeeklyTotal': family_weekly_total
            }, 200)
        # Events for a specific day (calendar view)
        if path == '/api/history' and self.command == 'GET':
            token = self._get_auth_token()
            if not token:
                return self._send_json({'error': 'missing token'}, 401)
            user = get_user_by_token(db, token)
            if not user:
                return self._send_json({'error': 'invalid token'}, 401)
            query = parse_qs(parsed.query)
            date_str = (query.get('date') or [None])[0]
            if date_str:
                try:
                    target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    return self._send_json({'error': 'invalid date'}, 400)
            else:
                target_date = _start_of_today().date()
            users_by_id = {u['id']: u for u in db['users']}
            events = []
            for ev in db['events']:
                if ev['householdId'] != user['householdId']:
                    continue
                if _event_date(ev['timestamp']) != target_date:
                    continue
                uinfo = users_by_id.get(ev['userId'])
                events.append({
                    'id': ev['id'],
                    'type': ev['type'],
                    'timestamp': ev['timestamp'],
                    'userId': ev['userId'],
                    'username': uinfo.get('username') if uinfo else None
                })
            events.sort(key=lambda e: e['timestamp'])
            return self._send_json({
                'date': target_date.isoformat(),
                'events': events
            }, 200)
        # Today's events and schedule status for the household
        if path == '/api/today' and self.command == 'GET':
            token = self._get_auth_token()
            if not token:
                logger.warning("GET /api/today - Missing token")
                return self._send_json({'error': 'missing token'}, 401)
            user = get_user_by_token(db, token)
            if not user:
                logger.warning("GET /api/today - Invalid token")
                return self._send_json({'error': 'invalid token'}, 401)
            logger.info(f"GET /api/today - User: {user['username']}")
            today = _start_of_today().date()
            # index users for name lookup
            users_by_id = {u['id']: u for u in db['users']}
            events = []
            for ev in db['events']:
                if ev['householdId'] != user['householdId']:
                    continue
                # only events from *today* in local time
                if _event_date(ev['timestamp']) != today:
                    continue
                uinfo = users_by_id.get(ev['userId'])
                events.append({
                    'id': ev['id'],
                    'type': ev['type'],
                    'timestamp': ev['timestamp'],
                    'userId': ev['userId'],
                    'username': uinfo.get('username') if uinfo else None
                })
            # basic schedule flags
            has_morning_feed = any(e['type'] == 'feed_morning' for e in events)
            has_evening_feed = any(e['type'] == 'feed_evening' for e in events)
            has_walk = any(e['type'] == 'walk' for e in events)
            has_pee = any(e['type'] == 'pee' for e in events)
            has_poop = any(e['type'] == 'poop' for e in events)

            # simple daily challenge for the current user: 3 potty events (pee/poop)
            potty_events = [
                e for e in events
                if e['userId'] == user['id'] and e['type'] in ('pee', 'poop')
            ]
            challenge_progress = len(potty_events)
            challenge_target = 3
            daily_challenge = {
                'id': 'potty_hero',
                'title': 'בצעו 3 פעמים פיפי/קקי היום',
                'target': challenge_target,
                'progress': challenge_progress,
                'completed': challenge_progress >= challenge_target,
            }

            logger.info(f"Returning {len(events)} events for today")
            return self._send_json({
                'events': events,
                'schedule': {
                    'hasMorningFeed': has_morning_feed,
                    'hasEveningFeed': has_evening_feed,
                    'hasWalk': has_walk,
                    'hasPee': has_pee,
                    'hasPoop': has_poop,
                },
                'dailyChallenge': daily_challenge
            }, 200)
        # Delete single event (admin or event owner)
        if path.startswith('/api/events/') and self.command == 'DELETE':
            token = self._get_auth_token()
            if not token:
                return self._send_json({'error': 'missing token'}, 401)
            user = get_user_by_token(db, token)
            if not user:
                return self._send_json({'error': 'invalid token'}, 401)
            event_id = path.split('/')[-1]
            event = next((e for e in db['events'] if e['id'] == event_id), None)
            if not event:
                return self._send_json({'error': 'event not found'}, 404)
            # Only admin or event owner can delete
            if not user.get('isAdmin') and event['userId'] != user['id']:
                return self._send_json({'error': 'permission denied'}, 403)
            db['events'] = [e for e in db['events'] if e['id'] != event_id]
            save_db(db)
            logger.info(f"Event {event_id} deleted by {user['username']}")
            scoreboard, family_total, family_weekly_total = compute_scoreboard(db, user['householdId'])
            return self._send_json({
                'success': True,
                'scoreboard': scoreboard,
                'familyTotal': family_total,
                'familyWeeklyTotal': family_weekly_total
            }, 200)
        # Reset all scores (admin only) - clears all events
        if path == '/api/admin/reset-scores' and self.command == 'POST':
            token = self._get_auth_token()
            if not token:
                return self._send_json({'error': 'missing token'}, 401)
            user = get_user_by_token(db, token)
            if not user:
                return self._send_json({'error': 'invalid token'}, 401)
            if not user.get('isAdmin'):
                return self._send_json({'error': 'admin only'}, 403)
            # Delete all events for this household
            household_id = user['householdId']
            db['events'] = [e for e in db['events'] if e['householdId'] != household_id]
            save_db(db)
            logger.info(f"All scores reset by admin {user['username']} for household {household_id}")
            return self._send_json({'success': True, 'message': 'כל הנקודות אופסו'}, 200)
        # Clear all events (admin only)
        if path == '/api/admin/clear-events' and self.command == 'POST':
            token = self._get_auth_token()
            if not token:
                return self._send_json({'error': 'missing token'}, 401)
            user = get_user_by_token(db, token)
            if not user:
                return self._send_json({'error': 'invalid token'}, 401)
            if not user.get('isAdmin'):
                return self._send_json({'error': 'admin only'}, 403)
            # Delete all events for this household
            household_id = user['householdId']
            initial_count = len([e for e in db['events'] if e['householdId'] == household_id])
            db['events'] = [e for e in db['events'] if e['householdId'] != household_id]
            save_db(db)
            logger.info(f"All {initial_count} events cleared by admin {user['username']} for household {household_id}")
            return self._send_json({'success': True, 'message': f'{initial_count} אירועים נמחקו'}, 200)
        # Unknown API path
        return self._send_json({'error': 'unknown endpoint'}, 404)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/'):
            return self._handle_api()
        # Serve static files from the client directory
        # Determine requested path relative to client directory
        rel_path = parsed.path.lstrip('/') or 'index.html'
        abs_path = os.path.join(CLIENT_DIR, rel_path)
        # prevent directory traversal
        abs_path = os.path.normpath(abs_path)
        if not abs_path.startswith(os.path.abspath(CLIENT_DIR)):
            self.send_response(403)
            self.end_headers()
            return
        if os.path.isdir(abs_path):
            abs_path = os.path.join(abs_path, 'index.html')
        if not os.path.exists(abs_path):
            self.send_response(404)
            self.end_headers()
            return
        # serve file
        self.send_response(200)
        # Determine content type based on extension
        ext = os.path.splitext(abs_path)[1].lower()
        content_types = {
            '.html': 'text/html; charset=utf-8',
            '.css': 'text/css; charset=utf-8',
            '.js': 'application/javascript; charset=utf-8',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon'
        }
        ctype = content_types.get(ext, 'application/octet-stream')
        self.send_header('Content-Type', ctype)
        # allow caching static files
        if ext in ['.html', '.css', '.js']:
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        with open(abs_path, 'rb') as fh:
            self.wfile.write(fh.read())

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/'):
            return self._handle_api()
        else:
            # unsupported
            self.send_response(405)
            self.end_headers()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/'):
            return self._handle_api()
        else:
            # unsupported
            self.send_response(405)
            self.end_headers()


def run_server(port):
    os.chdir(CLIENT_DIR)  # ensure relative file resolution works
    server_address = ('', port)
    httpd = HTTPServer(server_address, AppHandler)
    logger.info("=" * 60)
    logger.info(f"🐕 Dog Training App Server Starting")
    logger.info(f"Port: {port}")
    logger.info(f"Client dir: {CLIENT_DIR}")
    logger.info(f"Database: {DATA_FILE}")
    logger.info("=" * 60)
    print(f"Serving on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutdown initiated by user")
        print("Shutting down server...")
    finally:
        httpd.server_close()
        logger.info("Server stopped")


if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', '8000'))
    run_server(PORT)