#requires -Version 5.1
<#
.SYNOPSIS
Run the project's existing local checks. See docs/testing.md for setup.
.EXAMPLE
.\dev.ps1 check frontend
.EXAMPLE
.\dev.ps1 check backend -TestPath tests/test_streaming.py
.EXAMPLE
.\dev.ps1 check browser
#>
param(
    [ValidateSet('check', 'help')]
    [string]$Command = 'help',
    [ValidateSet('frontend', 'backend', 'browser', 'video')]
    [string]$Target,
    [string]$TestPath
)

if ($Command -eq 'help') {
    Write-Host 'Usage: .\dev.ps1 check <frontend|backend|browser|video> [-TestPath <test file or directory>]'
    Write-Host 'frontend: JavaScript tests + build:check (run npm run build to rebuild)'
    Write-Host 'backend:  isolated pytest suite; browser tests excluded'
    Write-Host 'browser:  build:check + Playwright using a disposable Firestore emulator'
    Write-Host 'video:    standalone scene checks and stills (setup: video/README.md; no TestPath)'
    Write-Host 'Setup and maintenance: docs/testing.md'
    exit 0
}

$ErrorActionPreference = 'Stop'
# Native exit codes are checked explicitly on both Windows PowerShell and pwsh.
$PSNativeCommandUseErrorActionPreference = $false
$devExitCode = 0
$savedEnvironment = @{}
$locationPushed = $false

function Set-DevEnvironment([string]$Name, $Value) {
    if (-not $savedEnvironment.ContainsKey($Name)) {
        $savedEnvironment[$Name] = [Environment]::GetEnvironmentVariable($Name, 'Process')
    }
    if ($null -eq $Value) {
        # PowerShell's .NET argument binder can turn null into an empty string;
        # newer runtimes preserve that as an environment entry. Remove it explicitly.
        Remove-Item -LiteralPath "Env:$Name" -ErrorAction SilentlyContinue
    }
    else {
        [Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
    }
}

function Find-DevCommand([string]$Name, [string]$Hint) {
    $found = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $found) { throw "Missing $Name. $Hint" }
    return $found.Source
}

function Invoke-DevStep([string]$Label, [string]$Executable, [string[]]$Arguments) {
    Write-Host "[dev] $Label"
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        $script:devExitCode = $LASTEXITCODE
        throw "$Label failed (exit $LASTEXITCODE)."
    }
}

try {
    if (-not $Target) { throw 'Choose frontend, backend, browser or video. Run .\dev.ps1 help.' }
    if ($Target -eq 'video' -and $TestPath) { throw 'check video runs the complete scene check and does not accept TestPath.' }
    Push-Location -LiteralPath $PSScriptRoot
    $locationPushed = $true

    $testRoot = switch ($Target) {
        'frontend' { 'tests/js' }
        'backend' { 'tests' }
        'browser' { 'tests/e2e' }
        'video' { 'video/src' }
    }
    $selectedTests = $testRoot
    if ($TestPath) {
        $resolvedTest = (Resolve-Path -LiteralPath $TestPath).ProviderPath
        $allowedRoot = (Resolve-Path -LiteralPath $testRoot).ProviderPath
        if ($resolvedTest -ne $allowedRoot -and -not $resolvedTest.StartsWith("$allowedRoot\", [StringComparison]::OrdinalIgnoreCase)) {
            throw "TestPath must be inside $testRoot."
        }
        $selectedTests = $resolvedTest.Substring($PSScriptRoot.Length + 1).Replace('\', '/')
        # Firebase emulators:exec accepts a shell command. Only a validated,
        # repository-relative path is ever interpolated into that command.
        if ($selectedTests -notmatch '^[a-zA-Z0-9_./-]+$') {
            throw 'TestPath must use letters, digits, underscores, hyphens, dots and path separators.'
        }
        if ($Target -eq 'backend' -and ($selectedTests -eq 'tests/e2e' -or $selectedTests.StartsWith('tests/e2e/', [StringComparison]::OrdinalIgnoreCase))) {
            throw 'Use check browser for tests/e2e.'
        }
    }

    if ($Target -in @('frontend', 'browser')) {
        $null = Find-DevCommand 'node' 'Install Node.js and add it to PATH.'
        $npm = Find-DevCommand 'npm.cmd' 'Install Node.js including npm.'
        if (-not (Test-Path -LiteralPath 'node_modules/vitest/vitest.mjs') -or -not (Test-Path -LiteralPath 'node_modules/esbuild/package.json')) {
            throw 'Frontend dependencies are missing. Run npm ci.'
        }
    }

    if ($Target -in @('backend', 'browser')) {
        $python = Join-Path $PSScriptRoot 'venv/Scripts/python.exe'
        if (-not (Test-Path -LiteralPath $python)) {
            throw 'Missing venv/Scripts/python.exe. Create it with python -m venv venv; see docs/testing.md.'
        }
        Invoke-DevStep 'Python test dependencies (setup: python -m pip install -r requirements-test.txt in venv)' $python @('-c', 'import pytest')
        # Do not inherit an E2E run into the backend suite, or UNIT_TEST_MODE
        # into a browser run. Restore the caller's environment in finally.
        Set-DevEnvironment 'RUN_E2E' $(if ($Target -eq 'browser') { '1' } else { $null })
        Set-DevEnvironment 'UNIT_TEST_MODE' $(if ($Target -eq 'backend') { '1' } else { $null })
        Set-DevEnvironment 'E2E_TEST_MODE' $(if ($Target -eq 'browser') { '1' } else { $null })
    }

    switch ($Target) {
        'video' {
            $videoNode = Find-DevCommand 'node' 'Install Node.js and add it to PATH; see video/README.md.'
            if (-not (Test-Path -LiteralPath 'video/node_modules/playwright-core/package.json')) {
                throw 'Video dependencies are missing. Run npm --prefix video ci; see video/README.md.'
            }
            Invoke-DevStep 'Video scene checks and stills' $videoNode @('video/src/render.cjs', '--stills')
        }
        'frontend' {
            $testArguments = @('test')
            if ($TestPath) { $testArguments += @('--', $selectedTests) }
            Invoke-DevStep 'JavaScript tests' $npm $testArguments
            Invoke-DevStep 'Frontend build freshness (fix: npm run build)' $npm @('run', 'build:check')
        }
        'backend' {
            Invoke-DevStep 'Backend tests' $python @('-m', 'pytest', $selectedTests, '-q')
        }
        'browser' {
            $firebase = Find-DevCommand 'firebase.cmd' 'Install the Firebase CLI as documented in tests/e2e/README.md.'
            if ($env:JAVA_HOME -and (Test-Path -LiteralPath (Join-Path $env:JAVA_HOME 'bin/java.exe'))) {
                Set-DevEnvironment 'PATH' ((Join-Path $env:JAVA_HOME 'bin') + [IO.Path]::PathSeparator + $env:PATH)
            }
            $java = Find-DevCommand 'java' 'Install Java 21+ and set JAVA_HOME or PATH.'
            Invoke-DevStep 'Java runtime' $java @('--version')
            $browserCheck = @'
from pathlib import Path
from playwright.sync_api import sync_playwright
import uvicorn
with sync_playwright() as p:
    if not Path(p.chromium.executable_path).is_file():
        raise SystemExit('Chromium is missing. Run venv/Scripts/python.exe -m playwright install chromium.')
'@
            Invoke-DevStep 'Browser dependencies (setup: requirements-e2e.txt)' $python @('-c', $browserCheck)
            Invoke-DevStep 'Frontend build freshness (fix: npm run build)' $npm @('run', 'build:check')

            # Read the existing configuration and safety contract rather than
            # maintaining a second copy of the emulator project or port here.
            $config = Get-Content -LiteralPath 'firebase.json' -Raw | ConvertFrom-Json
            $firestore = $config.emulators.firestore
            $emulatorHost = '{0}:{1}' -f $firestore.host, $firestore.port
            Set-DevEnvironment 'FIRESTORE_EMULATOR_HOST' $emulatorHost
            $project = & $python -c 'from app.core.e2e_profile import E2E_PROJECT_ID; print(E2E_PROJECT_ID)'
            if ($LASTEXITCODE -ne 0 -or "$project" -notmatch '^demo-[a-z0-9-]+$') {
                throw 'Could not read the demo project from app/core/e2e_profile.py.'
            }
            foreach ($name in @('GOOGLE_CLOUD_PROJECT', 'GCLOUD_PROJECT', 'FIREBASE_PROJECT_ID')) {
                Set-DevEnvironment $name $project
            }
            Set-DevEnvironment 'GOOGLE_APPLICATION_CREDENTIALS' $null
            Invoke-DevStep 'Emulator isolation' $python @('-c', 'from app.core.e2e_profile import assert_safe_e2e_environment; assert_safe_e2e_environment()')

            # Firebase owns startup and shutdown, including a failing pytest
            # command. No background process or second terminal is needed.
            $testCommand = "venv\Scripts\python.exe -m pytest $selectedTests -q"
            Invoke-DevStep 'Browser tests with temporary Firestore emulator' $firebase @(
                'emulators:exec', '--only', 'firestore', '--project', $project,
                '--config', 'firebase.json', '--non-interactive', $testCommand
            )
        }
    }
    Write-Host "[dev] OK: $Target"
}
catch {
    if ($devExitCode -eq 0) { $devExitCode = 1 }
    [Console]::Error.WriteLine("[dev] ERROR: $($_.Exception.Message)")
}
finally {
    foreach ($name in $savedEnvironment.Keys) {
        Set-DevEnvironment $name $savedEnvironment[$name]
    }
    if ($locationPushed) { Pop-Location }
}
exit $devExitCode
