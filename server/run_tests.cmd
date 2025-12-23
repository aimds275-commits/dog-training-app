@echo off
REM Run pytest from server folder
pushd "%~dp0"
python -m pytest -q .
popd
