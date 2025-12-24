#!/usr/bin/env python3
"""Clear all events in db.json (with backup).

Creates a backup named db.json.reset.bak.<timestamp> and replaces the
events array with an empty list. Run from the `server` directory.
"""
import json, os, shutil, datetime

HERE = os.path.dirname(__file__)
DB = os.path.join(HERE, 'db.json')

def main():
    if not os.path.exists(DB):
        print('db.json not found, aborting')
        return
    ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    bak = DB + f'.reset.bak.{ts}'
    shutil.copy2(DB, bak)
    print('Backup saved to', bak)
    with open(DB, 'r', encoding='utf-8') as fh:
        db = json.load(fh)
    db['events'] = []
    tmp = DB + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(db, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, DB)
    print('Cleared all events in', DB)

if __name__ == '__main__':
    main()
