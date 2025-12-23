# Run pytest against the server folder reliably from any working directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$serverPath = Join-Path $scriptDir 'server'
python -m pytest -q $serverPath
