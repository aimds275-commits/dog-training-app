#!/usr/bin/env python3
"""
Flask version of the dog training app server.
Compatible with both local development and PythonAnywhere deployment.
Maintains exact same behavior as the original HTTP server.
"""
from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
import json
import os
import uuid
import datetime
import logging
import sys

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

# Initialize Flask app
app = Flask(__name__, static_folder='../client', static_url_path='')
CORS(app, resources={r"/*": {"origins": "*"}})

DATA_FILE = os.path.join(os.path.dirname(__file__), 'db.json')

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
    """Compute rich per-user stats and family totals for a household."""
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

    # assemble result
    scoreboard = []
    for user_id, info in per_user.items():
        u = user_index[user_id]
        scoreboard.append({
            'userId': user_id,
            'username': u['username'],
            'totalPoints': info['totalPoints'],
            'weeklyPoints': info['weeklyPoints'],
            'streak': info['streak'],
        })
    scoreboard.sort(key=lambda x: x['totalPoints'], reverse=True)

    family_total = sum(row['totalPoints'] for row in scoreboard)
    family_weekly = sum(row['weeklyPoints'] for row in scoreboard)

    return {
        'scoreboard': scoreboard,
        'familyTotal': family_total,
        'familyWeeklyTotal': family_weekly
    }


def get_auth_token():
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.lower().startswith('bearer '):
        return auth_header.split(' ', 1)[1].strip()
    # fallback to query parameter
    return request.args.get('token')


# ============================================================================
# API Routes
# ============================================================================

@app.route('/api/register', methods=['POST'])
def api_register():
    """Register a new user."""
    data = request.get_json()
    logger.info("API Request: POST /api/register")
    
    if not data or not data.get('email') or not data.get('password'):
        logger.warning("Registration failed: missing email or password")
        return jsonify({'error': 'email and password required'}), 400
    
    db = load_db()
    email = data['email'].strip().lower()
    display_name = (data.get('username') or '').strip()
    password = data['password']
    invite_token = data.get('inviteToken')
    
    logger.info(f"Registering user: {email}, invite: {bool(invite_token)}")
    
    # Check if email already exists
    if any(u.get('email', '').lower() == email for u in db['users']):
        return jsonify({'error': 'email already exists'}), 400
    
    # Determine household
    household_id = None
    if invite_token:
        for h in db['households']:
            if invite_token in h.get('inviteTokens', []):
                household_id = h['id']
                break
        if household_id is None:
            return jsonify({'error': 'invalid invite token'}), 400
    
    # Create household if not provided
    if not household_id:
        household_id = uuid.uuid4().hex
        new_invite = uuid.uuid4().hex
        db['households'].append({
            'id': household_id,
            'dogName': '',
            'inviteTokens': [new_invite],
            'dogAgeMonths': 0,
            'dogPhotoUrl': ''
        })
    
    # Create user
    user_id = uuid.uuid4().hex
    token = uuid.uuid4().hex
    
    # Check if this is the first user in the household (becomes admin)
    is_admin = not any(u['householdId'] == household_id for u in db['users'])
    
    db['users'].append({
        'id': user_id,
        'username': display_name or email.split('@')[0],
        'email': email,
        'password': password,
        'householdId': household_id,
        'token': token,
        'isAdmin': is_admin
    })
    
    save_db(db)
    logger.info(f"User registered: {email}, admin: {is_admin}")
    
    household = get_household(db, household_id)
    scores = compute_scoreboard(db, household_id)
    
    return jsonify({
        'token': token,
        'userId': user_id,
        'username': display_name or email.split('@')[0],
        'email': email,
        'householdId': household_id,
        'dogName': household.get('dogName', ''),
        'isAdmin': is_admin,
        **scores
    })


@app.route('/api/login', methods=['POST'])
def api_login():
    """Login existing user."""
    data = request.get_json()
    logger.info("API Request: POST /api/login")
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'email and password required'}), 400
    
    db = load_db()
    email = data['email'].strip().lower()
    password = data['password']
    
    user = None
    for u in db['users']:
        if u.get('email', '').lower() == email and u.get('password') == password:
            user = u
            break
    
    if not user:
        logger.warning(f"Login failed for: {email}")
        return jsonify({'error': 'invalid credentials'}), 401
    
    logger.info(f"User logged in: {email}")
    household = get_household(db, user['householdId'])
    scores = compute_scoreboard(db, user['householdId'])
    
    return jsonify({
        'token': user['token'],
        'userId': user['id'],
        'username': user['username'],
        'email': user.get('email', ''),
        'householdId': user['householdId'],
        'dogName': household.get('dogName', ''),
        'isAdmin': user.get('isAdmin', False),
        **scores
    })


@app.route('/api/user', methods=['GET'])
def api_user():
    """Get current user info."""
    token = get_auth_token()
    if not token:
        return jsonify({'error': 'unauthorized'}), 401
    
    db = load_db()
    user = get_user_by_token(db, token)
    if not user:
        return jsonify({'error': 'invalid token'}), 401
    
    household = get_household(db, user['householdId'])
    scores = compute_scoreboard(db, user['householdId'])
    
    return jsonify({
        'userId': user['id'],
        'username': user['username'],
        'email': user.get('email', ''),
        'householdId': user['householdId'],
        'dogName': household.get('dogName', ''),
        'dogAgeMonths': household.get('dogAgeMonths'),
        'dogPhotoUrl': household.get('dogPhotoUrl'),
        'inviteTokens': household.get('inviteTokens', []),
        'isAdmin': user.get('isAdmin', False),
        **scores
    })


@app.route('/api/dog', methods=['POST'])
def api_dog():
    """Update dog profile."""
    token = get_auth_token()
    if not token:
        return jsonify({'error': 'unauthorized'}), 401
    
    db = load_db()
    user = get_user_by_token(db, token)
    if not user:
        return jsonify({'error': 'invalid token'}), 401
    
    data = request.get_json()
    household = get_household(db, user['householdId'])
    
    if 'dogName' in data:
        household['dogName'] = data['dogName']
    if 'dogAgeMonths' in data:
        household['dogAgeMonths'] = data['dogAgeMonths']
    if 'dogPhotoUrl' in data:
        household['dogPhotoUrl'] = data['dogPhotoUrl']
    
    save_db(db)
    scores = compute_scoreboard(db, user['householdId'])
    
    return jsonify({
        'dogName': household.get('dogName', ''),
        'dogAgeMonths': household.get('dogAgeMonths'),
        'dogPhotoUrl': household.get('dogPhotoUrl'),
        **scores
    })


@app.route('/api/events', methods=['POST'])
def api_events_post():
    """Record a new event."""
    token = get_auth_token()
    if not token:
        return jsonify({'error': 'unauthorized'}), 401
    
    db = load_db()
    user = get_user_by_token(db, token)
    if not user:
        return jsonify({'error': 'invalid token'}), 401
    
    data = request.get_json()
    event_type = data.get('type')
    
    if not event_type:
        return jsonify({'error': 'type required'}), 400
    
    logger.info(f"POST /api/events - User {user['username']} added event: {event_type}")
    
    event_id = uuid.uuid4().hex
    timestamp = datetime.datetime.now(datetime.UTC).timestamp()
    
    db['events'].append({
        'id': event_id,
        'householdId': user['householdId'],
        'userId': user['id'],
        'type': event_type,
        'timestamp': timestamp
    })
    
    save_db(db)
    scores = compute_scoreboard(db, user['householdId'])
    
    logger.info(f"Event recorded: {event_type}, new family total: {scores['familyTotal']}")
    
    return jsonify({
        'success': True,
        'eventId': event_id,
        **scores
    })


@app.route('/api/events/<event_id>', methods=['DELETE'])
def api_events_delete(event_id):
    """Delete a single event."""
    token = get_auth_token()
    if not token:
        return jsonify({'error': 'unauthorized'}), 401
    
    db = load_db()
    user = get_user_by_token(db, token)
    if not user:
        return jsonify({'error': 'invalid token'}), 401
    
    # Find and remove the event
    event = None
    for i, e in enumerate(db['events']):
        if e['id'] == event_id and e['householdId'] == user['householdId']:
            event = db['events'].pop(i)
            break
    
    if not event:
        return jsonify({'error': 'event not found'}), 404
    
    save_db(db)
    scores = compute_scoreboard(db, user['householdId'])
    
    logger.info(f"Event deleted: {event_id} by {user['username']}")
    
    return jsonify({
        'success': True,
        'message': 'Event deleted',
        **scores
    })


@app.route('/api/scores', methods=['GET'])
def api_scores():
    """Get scoreboard."""
    token = get_auth_token()
    if not token:
        return jsonify({'error': 'unauthorized'}), 401
    
    db = load_db()
    user = get_user_by_token(db, token)
    if not user:
        return jsonify({'error': 'invalid token'}), 401
    
    scores = compute_scoreboard(db, user['householdId'])
    return jsonify(scores)


@app.route('/api/today', methods=['GET'])
def api_today():
    """Get today's events and schedule status."""
    token = get_auth_token()
    if not token:
        return jsonify({'error': 'unauthorized'}), 401
    
    db = load_db()
    user = get_user_by_token(db, token)
    if not user:
        return jsonify({'error': 'invalid token'}), 401
    
    logger.info(f"GET /api/today - User: {user['username']}")
    
    today_start = _start_of_today()
    today_ts = today_start.timestamp()
    
    # Get today's events
    events = []
    schedule = {
        'hasMorningFeed': False,
        'hasEveningFeed': False,
        'hasWalk': False,
        'hasPee': False,
        'hasPoop': False
    }
    
    for event in db['events']:
        if event['householdId'] != user['householdId']:
            continue
        if event['timestamp'] >= today_ts:
            # Get username
            event_user = get_user_by_token(db, None)
            for u in db['users']:
                if u['id'] == event['userId']:
                    event_user = u
                    break
            
            events.append({
                'id': event['id'],
                'type': event['type'],
                'timestamp': event['timestamp'],
                'userId': event['userId'],
                'username': event_user['username'] if event_user else 'Unknown'
            })
            
            # Update schedule
            if event['type'] == 'feed_morning':
                schedule['hasMorningFeed'] = True
            elif event['type'] == 'feed_evening':
                schedule['hasEveningFeed'] = True
            elif event['type'] == 'walk':
                schedule['hasWalk'] = True
            elif event['type'] == 'pee':
                schedule['hasPee'] = True
            elif event['type'] == 'poop':
                schedule['hasPoop'] = True
    
    logger.info(f"Returning {len(events)} events for today")
    
    return jsonify({
        'events': events,
        'schedule': schedule
    })


@app.route('/api/history', methods=['GET'])
def api_history():
    """Get events for a specific date."""
    token = get_auth_token()
    if not token:
        return jsonify({'error': 'unauthorized'}), 401
    
    db = load_db()
    user = get_user_by_token(db, token)
    if not user:
        return jsonify({'error': 'invalid token'}), 401
    
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'date parameter required'}), 400
    
    try:
        target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'invalid date format'}), 400
    
    # Get events for the date
    events = []
    for event in db['events']:
        if event['householdId'] != user['householdId']:
            continue
        event_date = _event_date(event['timestamp'])
        if event_date == target_date:
            event_user = None
            for u in db['users']:
                if u['id'] == event['userId']:
                    event_user = u
                    break
            
            events.append({
                'id': event['id'],
                'type': event['type'],
                'timestamp': event['timestamp'],
                'userId': event['userId'],
                'username': event_user['username'] if event_user else 'Unknown'
            })
    
    return jsonify({'events': events})


@app.route('/api/invite', methods=['POST'])
def api_invite():
    """Generate a new invite token."""
    token = get_auth_token()
    if not token:
        return jsonify({'error': 'unauthorized'}), 401
    
    db = load_db()
    user = get_user_by_token(db, token)
    if not user:
        return jsonify({'error': 'invalid token'}), 401
    
    if not user.get('isAdmin'):
        return jsonify({'error': 'admin only'}), 403
    
    household = get_household(db, user['householdId'])
    new_token = uuid.uuid4().hex
    household['inviteTokens'].append(new_token)
    
    save_db(db)
    logger.info(f"New invite token generated for household {user['householdId']}")
    
    return jsonify({
        'token': new_token,
        'inviteTokens': household['inviteTokens']
    })


@app.route('/api/invite/reset', methods=['POST'])
def api_invite_reset():
    """Reset all invite tokens."""
    token = get_auth_token()
    if not token:
        return jsonify({'error': 'unauthorized'}), 401
    
    db = load_db()
    user = get_user_by_token(db, token)
    if not user:
        return jsonify({'error': 'invalid token'}), 401
    
    if not user.get('isAdmin'):
        return jsonify({'error': 'admin only'}), 403
    
    household = get_household(db, user['householdId'])
    new_token = uuid.uuid4().hex
    household['inviteTokens'] = [new_token]
    
    save_db(db)
    logger.info(f"Invite tokens reset for household {user['householdId']}")
    
    return jsonify({
        'inviteTokens': household['inviteTokens']
    })


@app.route('/api/admin/reset-scores', methods=['POST'])
def api_admin_reset_scores():
    """Admin: Reset all scores (delete all events)."""
    token = get_auth_token()
    if not token:
        return jsonify({'error': 'unauthorized'}), 401
    
    db = load_db()
    user = get_user_by_token(db, token)
    if not user:
        return jsonify({'error': 'invalid token'}), 401
    
    if not user.get('isAdmin'):
        return jsonify({'error': 'admin only'}), 403
    
    logger.info(f"All scores reset by admin {user['username']} for household {user['householdId']}")
    
    # Remove all events for this household
    db['events'] = [e for e in db['events'] if e['householdId'] != user['householdId']]
    save_db(db)
    
    scores = compute_scoreboard(db, user['householdId'])
    
    return jsonify({
        'success': True,
        'message': 'All scores reset',
        **scores
    })


@app.route('/api/admin/clear-events', methods=['POST'])
def api_admin_clear_events():
    """Admin: Clear all events."""
    token = get_auth_token()
    if not token:
        return jsonify({'error': 'unauthorized'}), 401
    
    db = load_db()
    user = get_user_by_token(db, token)
    if not user:
        return jsonify({'error': 'invalid token'}), 401
    
    if not user.get('isAdmin'):
        return jsonify({'error': 'admin only'}), 403
    
    # Count events before clearing
    event_count = len([e for e in db['events'] if e['householdId'] == user['householdId']])
    
    logger.info(f"All {event_count} events cleared by admin {user['username']} for household {user['householdId']}")
    
    # Remove all events for this household
    db['events'] = [e for e in db['events'] if e['householdId'] != user['householdId']]
    save_db(db)
    
    scores = compute_scoreboard(db, user['householdId'])
    
    return jsonify({
        'success': True,
        'message': f'{event_count} events cleared',
        **scores
    })


# ============================================================================
# Static File Routes
# ============================================================================

@app.route('/')
def index():
    """Serve the main HTML file."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def static_files(path):
    """Serve static files."""
    try:
        return send_from_directory(app.static_folder, path)
    except:
        # If file not found, return index.html for client-side routing
        return send_from_directory(app.static_folder, 'index.html')


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🐕 Dog Training App Server Starting (Flask)")
    logger.info(f"Port: 8000")
    logger.info(f"Client dir: {app.static_folder}")
    logger.info(f"Database: {DATA_FILE}")
    logger.info("=" * 60)
    
    # Run Flask server
    app.run(host='0.0.0.0', port=8000, debug=False)
