$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$activateScript = Join-Path $scriptDir 'venv\Scripts\Activate.ps1'

Push-Location $scriptDir
try {
    if (-not (Test-Path $activateScript)) {
        throw "Virtual environment activation script not found at '$activateScript'. Create it with 'py -3.13 -m venv venv' from the backend directory."
    }

    & $activateScript
    python -m uvicorn app.api:app --host 127.0.0.1 --port 8000 --reload @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}