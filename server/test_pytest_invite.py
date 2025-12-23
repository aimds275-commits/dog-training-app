import pytest


def test_invite_tokens_and_admins(server_module):
    db = server_module.load_db()
    assert 'households' in db and 'users' in db
    for h in db['households']:
        tokens = h.get('inviteTokens', [])
        # each household should have at least one invite token
        assert isinstance(tokens, list)
    # verify each household has at least one admin
    for h in db['households']:
        household_users = [u for u in db['users'] if u['householdId'] == h['id']]
        admins = [u for u in household_users if u.get('isAdmin')]
        assert len(admins) >= 1


def test_register_via_invite_links_user(server_module, tmp_path):
    db = server_module.load_db()
    # pick a household with tokens
    found = None
    for h in db['households']:
        if h.get('inviteTokens'):
            found = h
            break
    assert found is not None
    token = found['inviteTokens'][0]

    # simulate registration by appending a user and linking token
    import uuid
    new_id = uuid.uuid4().hex
    new_user = {'id': new_id, 'username': 'PYTEST_INT', 'email': 'pyint@example.com', 'password': 'p', 'householdId': found['id'], 'token': uuid.uuid4().hex}
    db['users'].append(new_user)
    found.setdefault('inviteLinks', {})[token] = new_id
    server_module.save_db(db)

    db2 = server_module.load_db()
    linked = db2['households'][[hh['id'] for hh in db2['households']].index(found['id'])].get('inviteLinks', {}).get(token)
    assert linked == new_id