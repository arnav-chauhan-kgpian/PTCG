# scripts/init_github.ps1
#
# One-shot: initialise the repo, verify the .gitignore is doing its job,
# and stage everything for the first commit. Does NOT push (you choose the
# remote URL). Run from the repo root.
#
# Usage:
#   pwsh ./scripts/init_github.ps1
#   pwsh ./scripts/init_github.ps1 -RemoteUrl git@github.com:you/pokemon-tcg-ai.git

[CmdletBinding()]
param(
    [string]$RemoteUrl = "",
    [string]$Branch = "main",
    [string]$Message = "Initial commit: production-ready Pokémon TCG AI framework"
)

$ErrorActionPreference = "Stop"

if (Test-Path .git) {
    Write-Host "Repo already initialised — skipping git init"
} else {
    Write-Host "→ git init"
    git init | Out-Null
    git branch -m $Branch
}

Write-Host ""
Write-Host "→ Verifying .gitignore (should NOT list venv/, node_modules/, .next/, .pdf, .pt, *.egg-info/)"
Write-Host "─────────────────────────────────────────────────────────────────────────────────"
$staged = git status --short
$problems = $staged | Select-String -Pattern "venv/|node_modules/|\.next/|Card_ID|\.pt$|\.egg-info/" -CaseSensitive:$false
if ($problems) {
    Write-Host "⚠ THE FOLLOWING SHOULD BE GITIGNORED BUT ARE STAGEABLE:" -ForegroundColor Yellow
    $problems | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
    Write-Host ""
    Write-Host "Stop and fix .gitignore before continuing." -ForegroundColor Red
    exit 1
} else {
    Write-Host "  OK — .gitignore catches the expected exclusions"
}

Write-Host ""
Write-Host "→ Sample of what WILL be committed (first 30 entries):"
Write-Host "─────────────────────────────────────────────────────────────"
$staged | Select-Object -First 30 | ForEach-Object { Write-Host "  $_" }
Write-Host "  ... ($($staged.Count) total entries)"

Write-Host ""
$confirm = Read-Host "Proceed with 'git add . && git commit'? [y/N]"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "Aborted by user."
    exit 0
}

Write-Host "→ git add ."
git add .

Write-Host "→ git commit -m `"$Message`""
git commit -m $Message | Out-Null

if ($RemoteUrl) {
    Write-Host "→ git remote add origin $RemoteUrl"
    git remote add origin $RemoteUrl 2>$null
    Write-Host "→ git push -u origin $Branch"
    git push -u origin $Branch
} else {
    Write-Host ""
    Write-Host "✓ Initial commit created. To push:" -ForegroundColor Green
    Write-Host "    git remote add origin <YOUR-GITHUB-URL>"
    Write-Host "    git push -u origin $Branch"
}
