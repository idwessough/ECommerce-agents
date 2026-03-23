<#
.SYNOPSIS
Runs the common Docker Compose flows for the market analysis scaffold.

.DESCRIPTION
Provides small wrappers around Docker Compose so the same entry points can be
used during local development on Windows and on macOS or Linux with the shell
variant.
#>
[CmdletBinding()]
param(
    [ValidateSet("help", "init-env", "config", "web", "api", "test")]
    [string]$Command = "help",
    [switch]$Build
)

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$EnvPath = Join-Path $ProjectRoot ".env"
$EnvExamplePath = Join-Path $ProjectRoot ".env.example"

function Write-Usage {
    @"
Usage:
  .\scripts\adk.ps1 init-env
  .\scripts\adk.ps1 config
  .\scripts\adk.ps1 web [-Build]
  .\scripts\adk.ps1 api [-Build]
  .\scripts\adk.ps1 test

Commands:
  init-env  Create .env from .env.example if it does not exist.
  config    Render the Docker Compose configuration.
  web       Start the ADK web UI on http://localhost:8001.
  api       Start the ADK API server on http://localhost:8000.
  test      Run the containerized pytest suite.
"@ | Write-Host
}

function Ensure-EnvFile {
    if (-not (Test-Path $EnvPath)) {
        Copy-Item $EnvExamplePath $EnvPath
        Write-Host "Created .env from .env.example. Replace GOOGLE_API_KEY before live analysis."
        return
    }

    Write-Host ".env already exists."
}

function Warn-IfMissingEnv {
    param([string]$Mode)

    if (-not (Test-Path $EnvPath) -and $Mode -in @("web", "api")) {
        Write-Warning "No .env file found. Compose defaults will let the service start, but live model calls need a real GOOGLE_API_KEY."
    }
}

function Invoke-Compose {
    param([string[]]$ComposeArgs)

    Push-Location $ProjectRoot
    try {
        & docker compose @ComposeArgs
    }
    finally {
        Pop-Location
    }
}

switch ($Command) {
    "help" {
        Write-Usage
    }
    "init-env" {
        Ensure-EnvFile
    }
    "config" {
        Invoke-Compose @("config")
    }
    "web" {
        Warn-IfMissingEnv -Mode "web"
        $composeArgs = @("--profile", "web", "up")
        if ($Build) {
            $composeArgs += "--build"
        }
        $composeArgs += "market-analysis-web"
        Invoke-Compose $composeArgs
    }
    "api" {
        Warn-IfMissingEnv -Mode "api"
        $composeArgs = @("up")
        if ($Build) {
            $composeArgs += "--build"
        }
        $composeArgs += "market-analysis-agent"
        Invoke-Compose $composeArgs
    }
    "test" {
        Invoke-Compose @("--profile", "test", "run", "--rm", "market-analysis-test")
    }
}