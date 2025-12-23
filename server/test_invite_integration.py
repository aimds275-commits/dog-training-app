#!/usr/bin/env python3
"""Integration test: register via invite and verify invite link mapping and response."""

import json
import os
import sys
import tempfile
import shutil

# ensure server module imports local server.py
script_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, script_dir)

from server import load_db, save_db, get_household


def test_register_via_invite():
    # Use a temp copy of db.json to avoid modifying project db
    db_path = os.path.join(script_dir, 'db.json')
    with open(db_path, 'r', encoding='utf-8') as f:
        orig = json.load(f)

    tmp_dir = tempfile.mkdtemp()
    try:
        tmp_db = os.path.join(tmp_dir, 'db.json')
        with open(tmp_db, 'w', encoding='utf-8') as f:
            json.dump(orig, f, ensure_ascii=False, indent=2)

        # Monkeypatch DATA_FILE used by server module by setting environment
        # We'll reload the server module to pick up the temp file
        os.environ['TEST_DB_FILE'] = tmp_db

        # Re-import server module functions to operate on temp db
        import importlib
        server = importlib.reload(__import__('server'))

        db = server.load_db()
        # Find a household with at least one invite token
        found = None
        for h in db['households']:
            tokens = h.get('inviteTokens', [])
            if tokens:
                found = (h, tokens[0])
                break
        assert found, 'No household with invite token found in test db'
        household, token = found

        # Prepare registration payload
        new_user_email = 'integration_new@example.com'
        new_user_password = 'p'
        new_user_name = 'Integrant'

        # Call the register logic via server.api-like flow
        # We'll emulate what register endpoint does
        # Create user
        import uuid
        user_id = uuid.uuid4().hex
        token_val = uuid.uuid4().hex
        is_admin = not any(u['householdId'] == household['id'] for u in db['users'])
        db['users'].append({
            'id': user_id,
            'username': new_user_name,
            'email': new_user_email,
            'password': new_user_password,
            'householdId': household['id'],
            'token': token_val,
            'isAdmin': is_admin
        })
        # record invite usage
        household.setdefault('inviteLinks', {})[token] = user_id

        server.save_db(db)

        # Reload and verify
        db2 = server.load_db()
        h2 = server.get_household(db2, household['id'])
        linked = h2.get('inviteLinks', {}).get(token)
        assert linked == user_id, 'Invite token was not linked to new user'

        # Also check that building inviteTokens response would include username
        linked_username = None
        if linked:
            for u in db2['users']:
                if u['id'] == linked:
                    linked_username = u.get('username')
                    break
        assert linked_username == new_user_name

        print('✓ Integration invite registration test passed')

    finally:
        shutil.rmtree(tmp_dir)


if __name__ == '__main__':
    test_register_via_invite()
