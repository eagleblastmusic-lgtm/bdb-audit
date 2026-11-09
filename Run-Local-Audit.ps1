# Current-user launch. No service installation, elevation, ACL or PKI changes.
param(
    [switch]$NoGui,
    [string]$Index
)
$ErrorActionPreference = 'Stop'
$taskPython = Join-Path $PSScriptRoot '.venv-f2\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    $taskPython = 'python'
}
$taskPreviousPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $PSScriptRoot 'src'
    $taskArguments = @('-P', '-m', 'bdb_audit', 'product', 'local', 'ui')
    if ($NoGui) { $taskArguments += '--no-gui' }
    if ($Index) { $taskArguments += @('--index', $Index) }
    & $taskPython @taskArguments
    exit $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $taskPreviousPath
}
