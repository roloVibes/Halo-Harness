#!/usr/bin/env pwsh
# install-halo.ps1 -- install Halo Harness (the successor of the pre-2.0
# tool) on Windows and make sure an old pre-2.0 install can never shadow
# it. Mirrors scripts/install-halo.sh (same steps, same flags, same spirit).
#
#   powershell -ExecutionPolicy ByPass -File install-halo.ps1   # clone, check out the LATEST TAG, install
#   .\install-halo.ps1 -Ref v2.0.7  # a specific tag (or branch / commit); -Ref master tracks master
#   .\install-halo.ps1 -Yes          # no questions (uninstalls an old pre-2.0 tool)
#   .\install-halo.ps1 -NoClone      # install straight from GitHub, no clone
#   .\install-halo.ps1 -NoModifyPath   # never edit the user PATH (or $env:HALO_NO_MODIFY_PATH=1)
#   .\install-halo.ps1 -DryRun       # print every command this script would
#                                     # run (installs, uninstalls, clone/pull),
#                                     # never actually runs them -- no network,
#                                     # no filesystem change, never prompts
#   .\install-halo.ps1 -CloneDir C:\src\Halo-Harness
#
# The default is the newest vX.Y.Z tag of the repository, never a moving branch;
# the script prints the tag and the commit it installs. With a clone, the
# dependencies are pinned to requirements.lock (exact versions: it is a
# constraints file, so uv pins versions but does not compare its hashes; CI
# installs it with --require-hashes).
#
# Step 5 may run `uv tool update-shell`, which adds ~\.local\bin to your user PATH.
# It asks first (auto-yes under -Yes), lets uv print what it changed, and is
# skipped with -NoModifyPath or HALO_NO_MODIFY_PATH=1, or when ~\.local\bin is
# already on your PATH. -DryRun prints it instead of running it.
#
# Needs: git, Python 3.10+. Installs uv if it is missing.
[CmdletBinding()]
param(
    [switch]$Yes,
    [switch]$NoClone,
    [switch]$DryRun,
    [switch]$NoModifyPath,
    [string]$Ref = "",
    [string]$CloneDir = $(if ($env:HALO_CLONE_DIR) { $env:HALO_CLONE_DIR } else { "$HOME\Halo-Harness" })
)

# The previous project's tool name, built from parts so this script never
# spells it out (2.0.5 round 2d: the old name is off the front pages).
$OldTool = "rolo" + "-claude"

$RepoUrl = "https://github.com/roloVibes/Halo-Harness.git"
$RepoUrlNoGit = "https://github.com/roloVibes/Halo-Harness"
$RawUrl = "https://raw.githubusercontent.com/roloVibes/Halo-Harness"
$UvInstallerVersion = "0.11.14"   # the uv bootstrap is version-pinned, never "latest"
# Deliberately NOT "Stop": several steps below call a native .exe (pip,
# git, uv) whose normal, non-fatal stderr chatter (progress output, a
# "not found" warning on a routine existence check) would otherwise be
# promoted into a script-ending exception. Every step that must actually
# stop the script on failure checks $LASTEXITCODE itself instead.
$ErrorActionPreference = "Continue"

function Say($msg) { Write-Host "`n==> $msg" }
function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

# Every REAL action (never a read-only detection) goes through Run -- prints
# the exact command instead of executing it under -DryRun. Only for plain
# argv-shaped external commands; a step with its own control flow (clone-or-
# pull, the uv self-installer) gets its own explicit dry-run branch instead.
function Run {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CommandParts)
    if ($DryRun) { Write-Host "DRY RUN: $($CommandParts -join ' ')" }
    else { & $CommandParts[0] @($CommandParts[1..($CommandParts.Length - 1)]) }
}

function Confirm($prompt) {
    if ($Yes) { return $true }
    if ($DryRun) { Write-Host "DRY RUN: would ask: $prompt [y/N]"; return $false }
    $r = Read-Host "$prompt [y/N]"
    return $r -match '^[Yy]'
}

# 1. Python 3.10+ (detection only -- real either way, -DryRun still needs the
#    real answer to decide whether it would even proceed).
$PyCmd = $null
foreach ($c in @("py", "python", "python3")) {
    if (Have $c) {
        $ok = & $c -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { $PyCmd = $c; break }
    }
}
if (-not $PyCmd) {
    Write-Host "Python 3.10 or newer is required (check: python --version)."
    exit 1
}
Say "Python: $(& $PyCmd --version)"

# 2. uv (isolated tool installs)
if (-not (Have "uv")) {
    if ($DryRun) {
        Say "DRY RUN: uv not found -- would install it: irm https://astral.sh/uv/$UvInstallerVersion/install.ps1 | iex"
    } else {
        Say "uv not found: installing it from https://astral.sh/uv"
        powershell -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/$UvInstallerVersion/install.ps1 | iex"
        $env:PATH = "$HOME\.local\bin;$env:PATH"
        if (-not (Have "uv")) { Write-Host "uv still not on PATH; open a new terminal and re-run."; exit 1 }
    }
} else {
    Say "uv: $(uv --version)"
}

# 3. Remove the old pre-2.0 tool so it can never run by mistake.
#    (halo migrates the old state directory to ~/.halo by itself on first
#    run.)
if ((uv tool list 2>$null) -match "^$OldTool ") {
    Say "Old pre-2.0 uv tool found"
    if (Confirm "Uninstall it (recommended)?") { Run uv tool uninstall $OldTool }
}
if ((Have "pipx") -and ((pipx list 2>$null) -match "package $OldTool")) {
    Say "Old pre-2.0 pipx install found"
    if (Confirm "Uninstall it (recommended)?") { Run pipx uninstall $OldTool }
}
& $PyCmd -m pip show $OldTool 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Say "Old pre-2.0 pip install found"
    if (Confirm "Uninstall it (recommended)?") { Run $PyCmd -m pip uninstall -y $OldTool }
}

# 3b. Which version: -Ref, else the newest vX.Y.Z tag -- never a moving branch.
#     Prints the tag and the commit that gets installed.
$RefSha = ""
function Resolve-Ref {
    if ($DryRun) {
        if (-not $script:Ref) {
            Write-Host "DRY RUN: git ls-remote --tags $RepoUrl   (the newest vX.Y.Z tag becomes the install ref)"
            $script:Ref = "<latest-tag>"
        } else {
            Write-Host "DRY RUN: would install ref $($script:Ref) (git ls-remote $RepoUrl resolves its commit)"
        }
        return
    }
    if (-not $script:Ref) {
        $tags = git ls-remote --tags $RepoUrl
        if ($LASTEXITCODE -ne 0 -or -not $tags) {
            Write-Host "Could not list the tags of $RepoUrl (network?). Re-run with -Ref <tag>."; exit 1
        }
        $names = @($tags | ForEach-Object { if ($_ -match 'refs/tags/(v[0-9][0-9.]*)$') { $Matches[1] } })
        if (-not $names) { Write-Host "No vX.Y.Z tag found at $RepoUrl. Re-run with -Ref <ref>."; exit 1 }
        $script:Ref = ($names | Sort-Object { [version]($_.Substring(1)) } | Select-Object -Last 1)
    }
    if ($script:Ref -match '^[0-9a-f]{40}$') {
        $script:RefSha = $script:Ref
    } else {
        $lines = @(git ls-remote $RepoUrl "refs/tags/$($script:Ref)" "refs/tags/$($script:Ref)^{}" "refs/heads/$($script:Ref)" 2>$null)
        $peeled = @($lines | Where-Object { $_ -like '*^{}' })
        $pick = if ($peeled.Count) { $peeled[0] } elseif ($lines.Count) { $lines[0] } else { "" }
        if ($pick) { $script:RefSha = ($pick -split '\s+')[0] }
    }
    $shown = if ($script:RefSha) { $script:RefSha } else { "resolved after checkout" }
    Say "Installing $($script:Ref) (commit $shown)"
}
Resolve-Ref

# 4. Install halo (2.0.1+ ships exactly one executable: halo)
if ($NoClone) {
    Say "Installing halo straight from GitHub at $Ref"
    Run uv tool install --reinstall --constraints "$RawUrl/$Ref/requirements.lock" "git+$RepoUrlNoGit@$Ref"
} else {
    if (Test-Path (Join-Path $CloneDir ".git")) {
        Say "Updating the clone at $CloneDir"
        if ($DryRun) { Write-Host "DRY RUN: git -C $CloneDir fetch --tags --force origin" }
        else { git -C $CloneDir fetch --tags --force origin }
    } else {
        Say "Cloning to $CloneDir"
        if ($DryRun) { Write-Host "DRY RUN: git clone $RepoUrl $CloneDir" }
        else { git clone $RepoUrl $CloneDir }
    }
    if ($DryRun) {
        Write-Host "DRY RUN: git -C $CloneDir checkout --detach $Ref"
    } else {
        $target = $Ref
        git -C $CloneDir rev-parse --verify -q "refs/remotes/origin/$Ref^{commit}" *> $null
        if ($LASTEXITCODE -eq 0) { $target = "origin/$Ref" }
        git -C $CloneDir checkout --detach $target
        if ($LASTEXITCODE -ne 0) { Write-Host "Could not check out $Ref in $CloneDir."; exit 1 }
        Say "Checked out $Ref at commit $(git -C $CloneDir rev-parse HEAD)"
    }
    Say "Installing halo from the clone (dependencies pinned by requirements.lock)"
    if ($DryRun) { Write-Host "DRY RUN: (cd $CloneDir && uv tool install --reinstall --constraints requirements.lock .)" }
    else { Push-Location $CloneDir; try { uv tool install --reinstall --constraints requirements.lock . } finally { Pop-Location } }
}

# 5. PATH for the uv tools directory. `uv tool update-shell` changes the user
#    PATH, so it is asked first (auto-yes under -Yes), uv's own output stays
#    visible, and -DryRun prints it instead of running it.
$LocalBin = "$HOME\.local\bin"
$OnPath = (($env:PATH -split ';') -contains $LocalBin)
$PathEdited = $false
if ($NoModifyPath -or $env:HALO_NO_MODIFY_PATH -eq "1") {
    Say "Not editing the user PATH (-NoModifyPath)"
} elseif ($OnPath) {
    Say "$LocalBin is already on your PATH; nothing to edit"
} elseif (Confirm "Add $LocalBin to your user PATH (uv tool update-shell edits it)?") {
    Run uv tool update-shell
    $PathEdited = $true
} elseif ($DryRun) {
    Write-Host "DRY RUN: uv tool update-shell   (only if you answer yes)"
}
$env:PATH = "$LocalBin;$env:PATH"
if (-not $OnPath -and -not $PathEdited) {
    Write-Host 'Add %USERPROFILE%\.local\bin to PATH (Settings > System > About > Advanced > Environment Variables), then open a new terminal.'
}

# 6. Verify: halo first on PATH, no pre-2.0 tool left anywhere on PATH
Say "Verify"
if ($DryRun) {
    Write-Host "DRY RUN: would check halo is on PATH, warn about a lingering pre-2.0 tool, then run: halo doctor"
} else {
    if (-not (Have "halo")) {
        Write-Host "halo is not on PATH yet: open a new terminal (uv tools live in %USERPROFILE%\.local\bin) and run: halo doctor"
        exit 1
    }
    $haloPath = (Get-Command halo).Source
    Write-Host "halo: $haloPath  ($(halo --version))"
    if (Have $OldTool) {
        $old = (Get-Command $OldTool).Source
        Write-Host "WARNING: an old pre-2.0 tool is still on PATH at $old."
        Write-Host "         Remove it so it cannot run by mistake (halo doctor names the exact command)."
    }
    try { halo doctor } catch {}
}

Say "Done. Next:"
Write-Host "  cd ~ ; halo init      # pick a provider (Databricks at work, OpenRouter at home), then a live pong"
Write-Host "  halo                  # the TUI, from any directory"
if (-not $NoClone) {
    Write-Host "Updates later:  re-run this installer (it installs the newest tag), or: .\install-halo.ps1 -Ref <tag>"
} else {
    Write-Host "Updates later:  re-run this installer, or: uv tool install --reinstall git+$RepoUrlNoGit@<tag>"
}
Write-Host "Or just:        halo update    (or /update inside halo)"
