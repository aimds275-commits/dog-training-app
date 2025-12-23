import shutil
import importlib
from pathlib import Path


def pytest_addoption(parser):
	# No custom options for now
	return


def server_module_factory(tmp_path):
	repo_dir = Path(__file__).parent
	orig_db = repo_dir / 'db.json'
	tmp_db = tmp_path / 'db.json'
	shutil.copy(orig_db, tmp_db)

	srv = importlib.import_module('server')
	# patch server module to use tmp db
	srv.DATA_FILE = str(tmp_db)
	srv._db_cache = None
	srv._db_cache_mtime = None
	# reload to ensure it picks up changes
	importlib.reload(srv)
	return srv


import pytest


@pytest.fixture
def server_module(tmp_path):
	return server_module_factory(tmp_path)


# Ignore legacy test scripts that aren't pytest-compatible
collect_ignore = ['test_server.py', 'test_invite.py', 'test_invite_integration.py']
