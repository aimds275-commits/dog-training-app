@echo off
REM Run pytest for the server folder from workspace root
python -m pytest -q "%~dp0server"
