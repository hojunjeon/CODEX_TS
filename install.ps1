$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$CctsHome = Join-Path $env:LOCALAPPDATA 'CCTS'
$CodexBin = Join-Path $CodexHome 'bin'
$SkillRoot = Join-Path $CodexHome 'skills'
$CctsSkill = Join-Path $SkillRoot 'custom-codex-token-saver'
$CompatSkill = Join-Path $SkillRoot 'codex-token-saver'
$Stamp = Get-Date -Format 'yyyyMMddHHmmss'

function Resolve-Python3 {
    $Candidates = @()
    $Py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($Py) {
        $Candidates += @{ Command = $Py.Source; Args = @('-3') }
    }
    $Python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($Python) {
        $Candidates += @{ Command = $Python.Source; Args = @() }
    }
    foreach ($Candidate in $Candidates) {
        $VersionArgs = @($Candidate.Args) + @('-c', 'import sys; print(sys.version_info[0])')
        $Output = & $Candidate.Command @VersionArgs 2>$null
        if ($LASTEXITCODE -eq 0 -and $Output -match '^3$') {
            return @{ Command = $Candidate.Command; Args = $Candidate.Args }
        }
    }
    throw "Python 3 was not found. Install Python 3, then rerun install.ps1."
}

function Copy-DirectoryClean {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination
    )
    if (-not (Test-Path $Source)) {
        throw "Missing source: $Source"
    }
    if (Test-Path $Destination) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $CctsHome, $CodexHome, $CodexBin, $SkillRoot | Out-Null
$PythonSpec = Resolve-Python3

Copy-DirectoryClean -Source (Join-Path $RepoRoot 'ccts') -Destination (Join-Path $CctsHome 'ccts')
Copy-DirectoryClean -Source (Join-Path $RepoRoot 'benchmarks') -Destination (Join-Path $CctsHome 'benchmarks')
if (Test-Path (Join-Path $RepoRoot 'docs')) {
    Copy-DirectoryClean -Source (Join-Path $RepoRoot 'docs') -Destination (Join-Path $CctsHome 'docs')
}
Copy-DirectoryClean -Source (Join-Path $RepoRoot 'skill\custom-codex-token-saver') -Destination $CctsSkill

if (Test-Path $CompatSkill) {
    $Backup = Join-Path $SkillRoot ("codex-token-saver.bak-ccts-" + $Stamp)
    Move-Item -LiteralPath $CompatSkill -Destination $Backup -Force
    Write-Host "Backed up legacy skill: $Backup"
}
New-Item -ItemType Directory -Force -Path $CompatSkill | Out-Null
@'
---
name: codex-token-saver
description: Compatibility alias. Use CCTS (custom codex token saver) for all Codex token-saving workflows.
---

# CCTS Compatibility Alias

The previous Codex Token Saver has been replaced by CCTS.

Use `ccts pack`, `ccts filter --capture`, `ccts get`, `ccts search`, `ccts ab-test`, and `ccts watchdog`.
'@ | Set-Content -Encoding UTF8 -Path (Join-Path $CompatSkill 'SKILL.md')

$CctsCmd = Join-Path $CodexBin 'ccts.cmd'
$PythonCommand = $PythonSpec.Command
$PythonPrefix = ''
if ($PythonSpec.Args.Count -gt 0) {
    $PythonPrefix = ($PythonSpec.Args -join ' ') + ' '
}
if (Test-Path $CctsCmd) {
    $Backup = $CctsCmd + ".bak-ccts-" + $Stamp
    Copy-Item -LiteralPath $CctsCmd -Destination $Backup -Force
    Write-Host "Backed up previous ccts shim: $Backup"
}
@"
@echo off
set "PYTHONPATH=%LOCALAPPDATA%\CCTS;%PYTHONPATH%"
"$PythonCommand" $PythonPrefix-m ccts %*
exit /b %ERRORLEVEL%
"@ | Set-Content -Encoding ASCII -Path $CctsCmd

$CtsCmd = Join-Path $CodexBin 'cts.cmd'
if (Test-Path $CtsCmd) {
    $Backup = $CtsCmd + ".bak-ccts-" + $Stamp
    Copy-Item -LiteralPath $CtsCmd -Destination $Backup -Force
    Write-Host "Backed up legacy cts shim: $Backup"
}
@"
@echo off
rem CCTS replaces the old cts command.
call "%USERPROFILE%\.codex\bin\ccts.cmd" %*
exit /b %ERRORLEVEL%
"@ | Set-Content -Encoding ASCII -Path $CtsCmd

$env:PYTHONPATH = "$CctsHome;$env:PYTHONPATH"
$DbPath = Join-Path $CctsHome 'context.sqlite'
& $CctsCmd install-hook --codex-home $CodexHome --db $DbPath --ccts-command "`"$CctsCmd`""
if ($LASTEXITCODE -ne 0) {
    throw "ccts install-hook failed with exit code $LASTEXITCODE"
}

Write-Host "CCTS installed globally."
Write-Host "  command: $CctsCmd"
Write-Host "  old cts alias: $CtsCmd"
Write-Host "  home: $CctsHome"
Write-Host "  skill: $CctsSkill"
Write-Host "Restart Codex Desktop to reload skills and hooks."
