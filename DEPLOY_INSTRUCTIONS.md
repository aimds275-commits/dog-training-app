# Deployment Instructions

## Local Development

### Using Flask Server (Recommended for Deployment Testing)

1. Install dependencies:
```bash
cd server
pip install -r requirements.txt
```

2. Run the Flask server:
```bash
python flask_server.py
```

Or use VS Code task: **Terminal → Run Task → "Run Dog Training App Server (Flask)"**

3. Access at: http://localhost:8000

### Using Original HTTP Server (Faster for Development)

```bash
cd server
python server.py
```

Or use VS Code task: **Terminal → Run Task → "Run Dog Training App Server"**

Both servers work identically and maintain the same behavior! Use the original server for daily development, and Flask server to test before deploying to PythonAnywhere.

## Deploy to PythonAnywhere

### Step 1: Upload Files

### Option A: Using Git (Recommended)

**Step 1: Initialize Git locally**

```bash
cd c:\Users\dshmaya\Downloads\dog-training-app\dog-training-app
git init
git add .
git commit -m "Initial commit - Dog Training App"
```

**Step 2: Create a repository on GitHub/GitLab/Bitbucket**

1. Go to [GitHub.com](https://github.com) (or GitLab/Bitbucket)
2. Click "New repository" or "+" → "New repository"
3. Name it: `dog-training-app`
4. **Important**: Do NOT initialize with README, .gitignore, or license
5. Keep it **Private** (recommended) or Public
6. Click "Create repository"

**Step 3: Push to your Git account**

GitHub will show you commands. Use these:

```bash
# Add your remote repository
git remote add origin https://github.com/YOUR_USERNAME/dog-training-app.git

# Push to GitHub
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username.

**Alternative Git providers:**

- **GitLab**: `https://gitlab.com/YOUR_USERNAME/dog-training-app.git`
- **Bitbucket**: `https://bitbucket.org/YOUR_USERNAME/dog-training-app.git`

**Step 4: Clone on PythonAnywhere**

On PythonAnywhere Bash console:

```bash
# If repository is public:
git clone https://github.com/aimds275-commits/dog-training-app.git

# If repository is private:
git clone https://github.com/YOUR_USERNAME/dog-training-app.git
```

When prompted:
- **Username**: Your GitHub username (e.g., `aimds275-commits`)
- **Password**: Use a **Personal Access Token** (NOT your Google password or GitHub password)

**Why Personal Access Token?**
Since you're using GitHub with Google account, GitHub doesn't allow password authentication anymore. You must use a Personal Access Token.

**Creating a Personal Access Token:**

1. Go to GitHub.com → Click your profile picture (top right)
2. Settings → Developer settings (bottom left)
3. Personal access tokens → **Tokens (classic)**
4. Click **"Generate new token (classic)"**
5. Give it a name: `PythonAnywhere Deployment`
6. Select expiration: **90 days** (or longer)
7. Select scopes: Check **`repo`** (full control of private repositories)
8. Scroll down and click **"Generate token"**
9. **COPY THE TOKEN IMMEDIATELY** - you won't see it again!
   - It looks like: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

**Using the Token on PythonAnywhere:**

When you run `git clone`, you'll be prompted:

```bash
Username for 'https://github.com': aimds275-commits
Password for 'https://aimds275-commits@github.com': [paste your token here]
```

**Important**: The token is your password - paste it when asked for password.

**Alternative: Clone with token in URL (skip prompts):**

```bash
git clone https://YOUR_TOKEN@github.com/YOUR_USERNAME/dog-training-app.git

# Example:
git clone https://ghp_xxxxxxxxxxxx@github.com/aimds275-commits/dog-training-app.git
cd dog-training-app
```

This method embeds the token in the URL so you won't be prompted for credentials.

**Option B: Upload via PythonAnywhere Files Tab**

If you prefer not to use Git:

1. Go to PythonAnywhere Dashboard → **Files** tab
2. Click **"Upload a file"**
3. Create directory structure:
   - Click "Directories" → Create new directory: `dog-training-app`
   - Navigate into it
   - Create subdirectories: `server` and `client`

4. Upload files:
   - In `server/` directory: Upload all files from your local `server/` folder
     - `flask_server.py`
     - `server.py`
     - `db.json`
     - `requirements.txt`
     - `wsgi.py`
   
   - In `client/` directory: Upload all files from your local `client/` folder
     - `index.html`
     - `app.js`
     - `style.css`
     - `service-worker.js`
     - `manifest.webmanifest`

5. Verify structure:
```
/home/YOUR_USERNAME/
└── dog-training-app/
    ├── server/
    │   ├── flask_server.py
    │   ├── server.py
    │   ├── db.json
    │   ├── requirements.txt
    │   └── wsgi.py
    └── client/
        ├── index.html
        ├── app.js
        ├── style.css
        ├── service-worker.js
        └── manifest.webmanifest
```

**Tip**: You can also zip the entire folder locally, upload the zip, and extract it on PythonAnywhere using the Bash console:
```bash
unzip dog-training-app.zip
```

### Step 2: Install Dependencies

In PythonAnywhere Bash console:

```bash
cd ~/dog-training-app/server
pip3 install --user -r requirements.txt
```

Expected output:
```
Successfully installed Flask-3.0.0 Flask-CORS-4.0.0
```

### Step 3: Configure Web App

**Important: Use Flask Quickstart, NOT Manual Configuration**

1. Go to **Web** tab → **Add a new web app**
2. Choose **Next** on domain selection
3. Select **Flask** framework
4. Select **Python 3.10** version
5. **Path to your Flask app**: Enter the FULL path to flask_server.py:
   ```
   /home/YOUR_USERNAME/dog-training-app/server/flask_server.py
   ```
   Replace `YOUR_USERNAME` with your PythonAnywhere username (e.g., `dogdshmaya`)
   
   **Example**: `/home/dogdshmaya/dog-training-app/server/flask_server.py`
   
   ⚠️ **Important**: The path MUST end in `.py` and point to the `flask_server.py` file!

6. Click **Next** - PythonAnywhere will automatically create the web app

**After creation, configure static files:**

7. Scroll down to **Static files** section
8. **REMOVE** the `/` mapping if it exists (this causes 404 on API calls!)
9. Add **ONE** mapping only:
   
   | URL | Directory |
   |-----|-----------|
   | `/static` | `/home/YOUR_USERNAME/dog-training-app/client` |

10. Click **Reload** button at the top

**Important**: Do NOT map `/` to the client folder - this will break API routes!

**If you already chose Manual Configuration instead:**

1. Click **WSGI configuration file** and replace content with:

```python
import sys
import os

# Add project directory to path
project_home = '/home/YOUR_USERNAME/dog-training-app/server'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# Set working directory
os.chdir(project_home)

# Import Flask app
from flask_server import app as application
```

2. Set **Source code**: `/home/YOUR_USERNAME/dog-training-app`
3. Set **Working directory**: `/home/YOUR_USERNAME/dog-training-app/server`
4. Configure static files as shown above

### Step 4: Test

Visit: `https://YOUR_USERNAME.pythonanywhere.com`

## Switching Between Servers Locally

Both servers maintain identical behavior:

**Flask Server (for deployment):**
```bash
python flask_server.py
## VS Code Tasks

Two tasks are available:

1. **Run Dog Training App Server** - Original HTTP server (faster for development)
2. **Run Dog Training App Server (Flask)** - Flask version (test before deployment)

To run:
- Press **Ctrl+Shift+P** → type "Run Task"
- Or **Terminal → Run Task**
- Select the desired task

Both run on port 8000 and work with the same database!
```

Both run on port 8000 and work with the same database and client files!

## VS Code Tasks

You can also use VS Code tasks:
- Press **Ctrl+Shift+B** or **Terminal → Run Task**
- Select "Run Dog Training App Server"

## Troubleshooting PythonAnywhere

### 500 Internal Server Error
- Check error log: Web tab → Log files → Error log
- Common issues:
  - Wrong Python version selected
  - Dependencies not installed
  - Wrong paths in WSGI config

### Static files not loading
- Verify static files mapping in Web tab
- Path should be: `/home/dogdshmaya/dog-training-app/client`

### Database not persisting
```bash
# Check permissions
chmod 644 /home/dogdshmaya/dog-training-app/server/db.json
```

### Import errors
```bash
# Reinstall dependencies
cd ~/dog-training-app/server
pip3 install --user -r requirements.txt
```

## Database Backup

Before deployment, backup your database:

```bash
# Local
copy server\db.json server\db.json.backup

# On PythonAnywhere
cp ~/dog-training-app/server/db.json ~/dog-training-app/server/db.json.backup
```

## Production Considerations

1. **Change passwords**: Users should change passwords after deployment
2. **HTTPS**: PythonAnywhere provides HTTPS automatically
3. **Backup**: Regularly backup `db.json`
4. **Logs**: Monitor `server.log` for issues

## Free Tier Limitations

## Testing Locally Before Deploy

### Method 1: Command Line

```bash
cd server
pip install -r requirements.txt
python flask_server.py
```

### Method 2: VS Code Task (Recommended)

1. Press **Ctrl+Shift+P** (or F1)
2. Type "Run Task"
3. Select **"Run Dog Training App Server (Flask)"**
4. Server starts on http://localhost:8000

### Verify All Features

Open http://localhost:8000 and test:

- ✅ Login/Register with email
- ✅ Recording events (poop, pee, walk, feeding)
- ✅ Timeline displays events
- ✅ Points system working
## Quick Deploy Checklist

### Pre-Deployment (Local)
- [ ] Test Flask server locally: Run "Run Dog Training App Server (Flask)" task
- [ ] Verify all features work in browser
- [ ] No errors in browser console
- [ ] Backup database: `copy server\db.json server\db.json.backup`

### PythonAnywhere Setup
- [ ] Code pushed to Git or uploaded to PythonAnywhere
- [ ] Navigate to server folder: `cd ~/dog-training-app/server`
- [ ] Dependencies installed: `pip3 install --user -r requirements.txt`
- [ ] Web app created with Manual configuration (Python 3.10)
- [ ] Source code path: `/home/YOUR_USERNAME/dog-training-app`
- [ ] Working directory: `/home/YOUR_USERNAME/dog-training-app/server`

### Configuration
- [ ] WSGI config updated with correct username in paths
- [ ] Static files configured: both `/static` and `/` mappings
- [ ] Database file exists: `ls ~/dog-training-app/server/db.json`
- [ ] File permissions correct: `chmod 644 ~/dog-training-app/server/db.json`

### Launch
- [ ] Click "Reload" button at top of Web tab
- [ ] Visit site: `https://YOUR_USERNAME.pythonanywhere.com`
- [ ] Test login/register
- [ ] Test recording events
- [ ] Test admin features
- [ ] Check error log if issues occur

### Post-Deployment
- [ ] Bookmark your site URL
- [ ] Change user passwords if needed
- [ ] Set up regular database backups
- [ ] Monitor server.log for errors
- Check Application tab → Service Workers - v16 active

### Once Confirmed

If everything works locally with Flask, it will work on PythonAnywhere! Deploy with confidence.
   - Login/Register
   - Recording events
   - Admin features
   - Family sharing

3. Check browser console for errors

4. Once confirmed working, deploy to PythonAnywhere

## Quick Deploy Checklist

- [ ] Code pushed to Git or uploaded to PythonAnywhere
- [ ] Dependencies installed: `pip3 install --user -r requirements.txt`
- [ ] Web app created with Manual configuration
- [ ] WSGI config updated with correct paths
- [ ] Static files configured
- [ ] Database file uploaded
- [ ] Reload button clicked
- [ ] Site tested: login, events, admin features

## Support

If issues occur:
1. Check PythonAnywhere error logs
2. Verify all paths are correct
3. Test locally with Flask first
4. Check that db.json exists and is readable
