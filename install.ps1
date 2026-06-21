$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$EftsHome = Join-Path $env:LOCALAPPDATA 'EFTS'
$CodexBin = Join-Path $CodexHome 'bin'
$SkillRoot = Join-Path $CodexHome 'skills'
$EftsSkill = Join-Path $SkillRoot 'efts'
$LegacySkill = Join-Path $SkillRoot 'codex-token-saver'
$LegacyHome = Join-Path $env:LOCALAPPDATA 'CodexTokenSaver'
$BackupRoot = Join-Path $CodexHome 'backups\efts-migration'
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

function Move-LegacyPath {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Label
    )
    if (-not (Test-Path $Path)) {
        return
    }
    New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
    $Name = Split-Path -Leaf $Path
    $Destination = Join-Path $BackupRoot ($Stamp + '-' + $Label + '-' + $Name)
    Move-Item -LiteralPath $Path -Destination $Destination -Force
    Write-Host "Removed legacy ${Label}: $Destination"
}

New-Item -ItemType Directory -Force -Path $EftsHome, $CodexHome, $CodexBin, $SkillRoot | Out-Null
$PythonSpec = Resolve-Python3

Copy-DirectoryClean -Source (Join-Path $RepoRoot 'efts') -Destination (Join-Path $EftsHome 'efts')
Copy-DirectoryClean -Source (Join-Path $RepoRoot 'benchmarks') -Destination (Join-Path $EftsHome 'benchmarks')
if (Test-Path (Join-Path $RepoRoot 'docs')) {
    Copy-DirectoryClean -Source (Join-Path $RepoRoot 'docs') -Destination (Join-Path $EftsHome 'docs')
}
Copy-DirectoryClean -Source (Join-Path $RepoRoot 'skill\efts') -Destination $EftsSkill

Move-LegacyPath -Path $LegacySkill -Label 'skill'

$EftsCmd = Join-Path $CodexBin 'efts.cmd'
$PythonCommand = $PythonSpec.Command
$PythonPrefix = ''
if ($PythonSpec.Args.Count -gt 0) {
    $PythonPrefix = ($PythonSpec.Args -join ' ') + ' '
}
if (Test-Path $EftsCmd) {
    $Backup = $EftsCmd + ".bak-efts-" + $Stamp
    Copy-Item -LiteralPath $EftsCmd -Destination $Backup -Force
    Write-Host "Backed up previous efts shim: $Backup"
}
@"
@echo off
set "PYTHONPATH=%LOCALAPPDATA%\EFTS;%PYTHONPATH%"
"$PythonCommand" $PythonPrefix-m efts %*
exit /b %ERRORLEVEL%
"@ | Set-Content -Encoding ASCII -Path $EftsCmd

$CtsCmd = Join-Path $CodexBin 'cts.cmd'
Move-LegacyPath -Path $CtsCmd -Label 'command'
Move-LegacyPath -Path $LegacyHome -Label 'home'

$env:PYTHONPATH = "$EftsHome;$env:PYTHONPATH"
$DbPath = Join-Path $EftsHome 'context.sqlite'
& $EftsCmd install-hook --codex-home $CodexHome --db $DbPath --efts-command "`"$EftsCmd`""
if ($LASTEXITCODE -ne 0) {
    throw "efts install-hook failed with exit code $LASTEXITCODE"
}

Write-Host "EFTS installed globally."
Write-Host "  command: $EftsCmd"
Write-Host "  home: $EftsHome"
Write-Host "  skill: $EftsSkill"
Write-Host "Restart Codex Desktop to reload skills and hooks."
