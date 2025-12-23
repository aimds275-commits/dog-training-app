#!/usr/bin/env python3
"""
WSGI entry point for PythonAnywhere deployment.
"""
import sys
import os

# Add your project directory to the sys.path
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# Change to the project directory
os.chdir(project_home)

# Import the Flask application
from flask_server import app as application
