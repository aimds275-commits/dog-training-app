#!/usr/bin/env python3
"""Fix admin status for existing users"""

import json
import os

def fix_admin_status():
    """Make the first user in each household an admin"""
    db_path = os.path.join(os.path.dirname(__file__), 'db.json')
    
    # Load database
    with open(db_path, 'r', encoding='utf-8') as f:
        db = json.load(f)
    
    print("Fixing admin status...")
    print(f"Households: {len(db['households'])}, Users: {len(db['users'])}")
    
    # For each household, make the first user an admin if no admin exists
    for h in db['households']:
        household_users = [u for u in db['users'] if u['householdId'] == h['id']]
        admins = [u for u in household_users if u.get('isAdmin')]
        
        if len(admins) == 0 and len(household_users) > 0:
            # Make first user admin
            first_user = household_users[0]
            first_user['isAdmin'] = True
            print(f"✅ Made '{first_user['username']}' admin of household {h['id'][:8]}")
    
    # Save database
    with open(db_path, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    
    print("\nDatabase updated successfully!")

if __name__ == '__main__':
    fix_admin_status()
