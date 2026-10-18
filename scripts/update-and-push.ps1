param(
    [string]$ApiBase = "http://127.0.0.1:8000",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = if ($env:PYTHON) { $env:PYTHON } else {
    if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
}

& $python -m src.build --api-base $ApiBase
if ($LASTEXITCODE -ne 0) { throw "build failed" }

git add dist/index.html
if (-not (git diff --cached --quiet)) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
    git commit -m "data: refresh $stamp"
} else {
    Write-Host "no data changes"
    exit 0
}

$remote = git remote get-url origin 2>$null
if (-not $remote) {
    throw "no git remote 'origin'; add the GitHub SSH URL first"
}
git push origin $Branch
