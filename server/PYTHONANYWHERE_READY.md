Checklist for PythonAnywhere deployment

- [x] Flask app is provided in `flask_server.py` and exposes `app`.
- [x] `wsgi.py` imports the Flask `app` as `application`.
- [x] Paths to `db.json` and `client` are resolved relative to `__file__`.
- [x] `requirements.txt` lists `Flask` and `Flask-CORS`.

Recommended next steps on PythonAnywhere:

1. Create a virtualenv and install requirements:

```bash
python3.10 -m venv ~/venvs/dog-training-app
source ~/venvs/dog-training-app/bin/activate
pip install -r ~/dog-training-app/server/requirements.txt
```

2. Configure the Web app:
   - Working directory: `/home/YOUR_USERNAME/dog-training-app/server`
   - WSGI file: ensure it contains `from flask_server import app as application`
   - Static files mapping: URL `/` -> `/home/YOUR_USERNAME/dog-training-app/client`

3. Move `db.json` to a data directory if desired and update `TEST_DB_FILE` or set `DB_FILE` env var.

Notes:
- Free accounts cannot use Always-On tasks; use the WSGI web app.
- File permissions on PythonAnywhere should allow the web app to write to `db.json`.
