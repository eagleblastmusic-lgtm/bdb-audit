# Current-user launch. No service installation, elevation, ACL or PKI changes.
$ErrorActionPreference = 'Stop'
$taskPython = Join-Path $PSScriptRoot '.venv-f2\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    $taskPython = 'python'
}
$taskPreviousPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $PSScriptRoot 'src'
    & $taskPython -m bdb_audit product local ui
    exit $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $taskPreviousPath
}
