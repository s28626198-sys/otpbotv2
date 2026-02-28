param(
    [string]$RepoUrl = "https://github.com/s28626198-sys/otpbotv2.git",
    [string]$Branch = "main",
    [string]$CommitMessage = "Deploy-ready: Docker + Render web service config"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (-not (Test-Path ".git")) {
    git init
}

git add .

$pending = git diff --cached --name-only
if (-not $pending) {
    Write-Host "No staged changes to commit." -ForegroundColor Yellow
} else {
    git commit -m $CommitMessage
}

git branch -M $Branch

$hasOrigin = git remote | Where-Object { $_ -eq "origin" }
if (-not $hasOrigin) {
    git remote add origin $RepoUrl
} else {
    git remote set-url origin $RepoUrl
}

git push -u origin $Branch
