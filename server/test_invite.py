#!/usr/bin/env python3
"""Test invite system functionality"""

import json
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_invite_system():
    """Test that invite system works correctly"""
    print("=" * 60)
    print("Testing Invite System")
    print("=" * 60)
    
    # Load database
    db_path = os.path.join(os.path.dirname(__file__), 'db.json')
    with open(db_path, 'r', encoding='utf-8') as f:
        db = json.load(f)
    
    print(f"\n1. Database loaded: {len(db['households'])} households, {len(db['users'])} users")
    
    # Check households and their invite tokens
    print("\n2. Household Invite Tokens:")
    for h in db['households']:
        print(f"   Household ID: {h['id'][:8]}...")
        print(f"   Dog Name: {h.get('dogName', 'N/A')}")
        print(f"   Invite Tokens: {h.get('inviteTokens', [])}")
        print()
    
    # Check users and admin status
    print("3. Users and Admin Status:")
    for u in db['users']:
        print(f"   User: {u['username']}")
        print(f"   Email: {u.get('email', 'N/A')}")
        print(f"   Household ID: {u['householdId'][:8]}...")
        print(f"   Is Admin: {u.get('isAdmin', False)}")
        print(f"   Token: {u['token'][:8]}...")
        print()
    
    # Verify each household has at least one admin
    print("4. Admin Verification:")
    for h in db['households']:
        household_users = [u for u in db['users'] if u['householdId'] == h['id']]
        admins = [u for u in household_users if u.get('isAdmin')]
        print(f"   Household {h['id'][:8]}: {len(household_users)} users, {len(admins)} admins")
        if len(admins) == 0:
            print(f"   ⚠️  WARNING: No admin in household {h['id'][:8]}")
        else:
            print(f"   ✅ Admin(s): {', '.join(a['username'] for a in admins)}")
    
    # Check if households have invite tokens
    print("\n5. Invite Token Check:")
    for h in db['households']:
        tokens = h.get('inviteTokens', [])
        if not tokens:
            print(f"   ⚠️  Household {h['id'][:8]} has NO invite tokens")
        else:
            print(f"   ✅ Household {h['id'][:8]} has {len(tokens)} invite token(s)")
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

if __name__ == '__main__':
    test_invite_system()
