# Deploy Dog Training App to PythonAnywhere

## Prerequisites

1. Create a free account at [www.pythonanywhere.com](https://www.pythonanywhere.com)
2. Verify your email address

## Step 1: Upload Files

### Option A: Using Git (Recommended)

1. Push your code to GitHub:
```bash
cd c:\Users\dshmaya\Downloads\dog-training-app\dog-training-app
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/dog-training-app.git
git push -u origin main
```

2. On PythonAnywhere, open a Bash console and clone:
```bash
git clone https://github.com/YOUR_USERNAME/dog-training-app.git
cd dog-training-app
```

### Option B: Manual Upload

1. Go to PythonAnywhere Dashboard → Files
2. Create a new directory: `dog-training-app`
3. Upload all files:
   - `server/server.py`
   - `server/db.json`
   - `client/` folder (all files)

## Step 2: Modify server.py for PythonAnywhere

Create a new file `server/wsgi.py`:

```python
#!/usr/bin/env python3
"""
WSGI application for PythonAnywhere deployment.
"""
import sys
import os

# Add your project directory to the sys.path
project_home = '/home/YOUR_USERNAME/dog-training-app/server'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# Set the working directory
os.chdir(project_home)

# Import the Flask/WSGI app
from server import application

# PythonAnywhere needs an 'application' variable
# We'll need to convert our HTTP server to Flask/Django
```

**IMPORTANT**: The current `server.py` uses Python's built-in HTTP server which won't work on PythonAnywhere. You need to convert it to Flask or Django.

## Step 3: Convert to Flask (Recommended)

Create a new file `server/flask_app.py`:

```python
#!/usr/bin/env python3
"""
Flask version of the dog training app for PythonAnywhere deployment.
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import uuid
import datetime
import logging

app = Flask(__name__, static_folder='../client')
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), 'db.json')

# Database cache
_db_cache = None
_db_cache_mtime = None

def load_db():
    """Load database with caching."""
    global _db_cache, _db_cache_mtime
    
    if not os.path.exists(DATA_FILE):
        _db_cache = {'households': [], 'users': [], 'events': []}
        _db_cache_mtime = None
        return _db_cache
    
    current_mtime = os.path.getmtime(DATA_FILE)
    if _db_cache is not None and _db_cache_mtime == current_mtime:
        return _db_cache
    
    with open(DATA_FILE, 'r', encoding='utf-8') as fh:
        _db_cache = json.load(fh)
        _db_cache_mtime = current_mtime
        return _db_cache

def save_db(db):
    """Save database and update cache."""
    global _db_cache, _db_cache_mtime
    tmp_file = DATA_FILE + '.tmp'
    with open(tmp_file, 'w', encoding='utf-8') as fh:
        json.dump(db, fh, indent=2, ensure_ascii=False)
    os.replace(tmp_file, DATA_FILE)
    _db_cache = db
    _db_cache_mtime = os.path.getmtime(DATA_FILE)

# Copy all your API endpoint logic here...
# Convert self._send_json() to return jsonify()
# Convert self._read_json() to request.get_json()
# etc.

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    app.run(debug=True)
```

## Step 4: Install Dependencies

On PythonAnywhere Bash console:

```bash
pip3 install --user flask flask-cors
```

## Step 5: Configure Web App

1. Go to PythonAnywhere Dashboard → Web
2. Click "Add a new web app"
3. Choose "Manual configuration" → Python 3.10
4. Configure:
   - **Source code**: `/home/YOUR_USERNAME/dog-training-app`
   - **Working directory**: `/home/YOUR_USERNAME/dog-training-app/server`
   - **WSGI configuration file**: Click to edit

Replace the WSGI file content with:

```python
import sys
import os

# Add your project directory
project_home = '/home/YOUR_USERNAME/dog-training-app/server'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

os.chdir(project_home)

from flask_app import app as application
```

5. Set **Static files**:
   - URL: `/`
   - Directory: `/home/YOUR_USERNAME/dog-training-app/client`

6. Click "Reload" button

## Step 6: Security Setup

1. **Change default database location** (optional):
```bash
# On PythonAnywhere
mkdir -p /home/YOUR_USERNAME/data
mv db.json /home/YOUR_USERNAME/data/
# Update DATA_FILE path in flask_app.py
```

2. **Set proper permissions**:
```bash
chmod 600 /home/YOUR_USERNAME/data/db.json
```

3. **Add environment variables** (in WSGI config):
```python
os.environ['SECRET_KEY'] = 'your-secret-key-here'
```

## Alternative: Use PythonAnywhere's Always-On Tasks

If you want to keep the HTTP server as-is:

1. Go to Tasks tab
2. Create a scheduled task:
```bash
cd /home/YOUR_USERNAME/dog-training-app/server && python3 server.py
```

**Note**: Free accounts can't use Always-On tasks. You'll need a paid account.

## Simpler Solution: Convert to Flask

Since PythonAnywhere requires WSGI apps, I recommend creating a Flask version. Would you like me to:

1. Create a complete Flask conversion of your `server.py`?
2. Generate all the necessary WSGI configuration files?
3. Create a deployment script to automate the upload?

Let me know and I'll generate the complete Flask app for you!

## Quick Start Commands

```bash
# On PythonAnywhere Bash console
cd ~
git clone YOUR_REPO_URL dog-training-app
cd dog-training-app/server
pip3 install --user flask flask-cors
```

Then configure the web app as described in Step 5.

## Troubleshooting

- **500 Error**: Check error logs in PythonAnywhere dashboard
- **Static files not loading**: Verify static files mapping
- **Database not persisting**: Check file permissions
- **Import errors**: Ensure all dependencies installed with `pip3 install --user`

## Free Tier Limitations

- One web app only
- Limited CPU seconds per day
- No always-on tasks
- yourname.pythonanywhere.com domain

For production, consider upgrading to a paid plan.
