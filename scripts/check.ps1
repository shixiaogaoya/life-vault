$ErrorActionPreference = "Stop"

$Python = $env:LIFEVAULT_PYTHON
if (-not $Python) {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCommand) {
        $Python = $PythonCommand.Source
    }
}
if (-not $Python) {
    $PyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($PyCommand) {
        $Python = $PyCommand.Source
    }
}
if (-not $Python) {
    throw "Python was not found. Install Python 3.11+ or set LIFEVAULT_PYTHON to your python.exe path."
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Command,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]] $Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command $($Arguments -join ' ')"
    }
}

Push-Location "$PSScriptRoot\..\backend"
try {
    Invoke-Checked $Python -m pytest tests -q
}
finally {
    Pop-Location
}

Push-Location "$PSScriptRoot\..\frontend"
try {
    Invoke-Checked "npm" run build
}
finally {
    Pop-Location
}

Invoke-Checked $Python "$PSScriptRoot\e2e_check.py"
