param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$studioPython = Join-Path $studioRoot 'runtime/python/python.exe'
$studioPython = [IO.Path]::GetFullPath($studioPython)
$studioIdentity = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Join-Path $studioRoot 'data')))
if (-not $CheckOnly) {
    $studioActivity = & $studioPython (Join-Path $studioRoot 'scripts/workbench_runtime.py')
    if ($LASTEXITCODE -ne 0) { throw 'Could not check active work; backend was not stopped.' }
    $studioActivity = $studioActivity | ConvertFrom-Json
    if ($studioActivity.busy) { throw "Workspace is busy: jobs=$($studioActivity.jobs), assistant=$($studioActivity.assistant), deployment=$($studioActivity.deployment). Finish or cancel this work before restarting." }
}
# server.json can hold a stale PID; identify the actual launcher and workspace.
$studioCandidates = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
    $_.ExecutablePath -eq $studioPython -and $_.CommandLine -match '(?:^|\s)-m\s+uvicorn\s+app\.main:app(?:\s|$)'
})
$studioFound = $false
foreach ($studioProcess in $studioCandidates) {
    if ($studioProcess.CommandLine -notmatch '--port\s+(\d+)') { continue }
    $studioPort = [int]$Matches[1]
    try {
        $studioHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$studioPort/api/health" -TimeoutSec 15
    } catch {
        Write-Warning "Cannot verify workspace on port $studioPort; process was not stopped."
        continue
    }
    if ($studioHealth.workspace_id -ne $studioIdentity) { continue }
    if (-not $CheckOnly -and $studioHealth.activity.busy) { throw 'Workspace became busy; backend was not stopped.' }
    $studioFound = $true
    if ($CheckOnly) {
        [PSCustomObject]@{ProcessId=$studioProcess.ProcessId;Port=$studioPort;WorkspaceVerified=$true}
    } else {
        & taskkill.exe /PID $studioProcess.ProcessId /T /F
        if ($LASTEXITCODE -ne 0) { throw 'Could not stop the workspace backend.' }
    }
}
if (-not $studioFound) { Write-Output 'No verified backend is running for this workspace.' }
