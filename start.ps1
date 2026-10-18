param([switch]$BackendOnly, [switch]$Restart)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$studioRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
function Get-StudioActivity {
    $studioCheckPython = Join-Path $studioRoot 'runtime/python/python.exe'
    $studioActivityOutput = & $studioCheckPython (Join-Path $studioRoot 'scripts/workbench_runtime.py')
    if ($LASTEXITCODE -ne 0) { throw 'Could not verify active work; restart was not performed.' }
    return ($studioActivityOutput | ConvertFrom-Json)
}
function Assert-StudioIdle {
    $studioWork = Get-StudioActivity
    if ($studioWork.busy) {
        throw "Work is still running (jobs=$($studioWork.jobs), assistant=$($studioWork.assistant), deployment=$($studioWork.deployment)). Finish or cancel it before restarting."
    }
}
function Test-StudioListener([int]$Port) {
    $studioSocket = New-Object Net.Sockets.TcpClient
    try {
        $studioConnect = $studioSocket.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $studioConnect.AsyncWaitHandle.WaitOne(100)) { return $false }
        $studioSocket.EndConnect($studioConnect)
        return $true
    } catch { return $false }
    finally { $studioSocket.Close() }
}
if (-not $BackendOnly) {
    if ($Restart) {
        Assert-StudioIdle
        $studioExecutable = Join-Path $studioRoot 'AI漫剧工作台.exe'
        # Close this workspace's window normally, preserving its save check.
        $studioWindows = @(Get-CimInstance Win32_Process -Filter "Name='AI漫剧工作台.exe'" | Where-Object { $_.ExecutablePath -eq $studioExecutable })
        # An update build can have a different filename but shares this workspace.
        try {
            $studioDesktopState = Get-Content -LiteralPath (Join-Path $studioRoot 'data/desktop-state.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            $studioStateProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($studioDesktopState.pid)" -ErrorAction Stop
            if ($studioStateProcess -and $studioStateProcess.Name.StartsWith('AI') -and [IO.Path]::GetDirectoryName($studioStateProcess.ExecutablePath) -eq $studioRoot -and $studioDesktopState.workspace.TrimEnd('\') -eq $studioRoot) {
                $studioWindows += $studioStateProcess
            }
        } catch {}
        foreach ($studioWindow in @($studioWindows | Sort-Object ProcessId -Unique)) {
            $studioDesktop = Get-Process -Id $studioWindow.ProcessId -ErrorAction Stop
            if (-not $studioDesktop.CloseMainWindow()) { throw 'The workspace window could not close normally; restart was not performed.' }
            if (-not $studioDesktop.WaitForExit(20000)) { throw 'The window is still open. Resolve its save prompt, then retry restart.' }
        }
        $studioRestartStatePath = Join-Path $studioRoot 'data/server.json'
        $studioBeforeRestart = $null
        try {
            $studioBeforeState = Get-Content -LiteralPath $studioRestartStatePath -Raw -Encoding UTF8 | ConvertFrom-Json
            $studioBeforeRestart = Invoke-RestMethod -Uri "http://127.0.0.1:$($studioBeforeState.port)/api/health" -TimeoutSec 15
        } catch {}
        $studioRestartHelper = Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$PSCommandPath+'"'),'-BackendOnly','-Restart') -WorkingDirectory $studioRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $studioRoot 'data/restart-startup.log') -RedirectStandardError (Join-Path $studioRoot 'data/restart-startup-error.log')
        $studioRestartReady = $false
        $studioRestartDeadline = (Get-Date).AddSeconds(60)
        do {
            Start-Sleep -Milliseconds 250
            try {
                $studioAfterState = Get-Content -LiteralPath $studioRestartStatePath -Raw -Encoding UTF8 | ConvertFrom-Json
                $studioAfterHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$($studioAfterState.port)/api/health" -TimeoutSec 1
                if ($studioAfterHealth.runtime_id -and $studioAfterHealth.runtime_id -ne $studioBeforeRestart.runtime_id -and $studioAfterState.runtime_id -eq $studioAfterHealth.runtime_id) {
                    $studioRestartReady = $true
                    break
                }
            } catch {}
            if ($studioRestartHelper.HasExited -and $studioRestartHelper.ExitCode -ne 0) { throw 'Backend restart failed; see data/restart-startup-error.log.' }
        } while ((Get-Date) -lt $studioRestartDeadline)
        if (-not $studioRestartReady) { throw 'Restart did not become ready within 60 seconds; see data/restart-startup-error.log.' }
        # The server is detached. End only our own completed startup helper if
        # PowerShell is still retaining its process streams after reporting ready.
        if (-not $studioRestartHelper.WaitForExit(2000)) {
            $studioRestartHelper.Kill()
            $studioRestartHelper.WaitForExit(2000) | Out-Null
        }
        $studioRestartHelper.Dispose()
    }
    $studioWindowInfo = New-Object Diagnostics.ProcessStartInfo
    $studioWindowInfo.FileName = Join-Path $studioRoot 'AI漫剧工作台.exe'
    $studioWindowInfo.WorkingDirectory = $studioRoot
    $studioWindowInfo.UseShellExecute = $false
    $studioWindowInfo.WindowStyle = [Diagnostics.ProcessWindowStyle]::Normal
    $studioNewWindow = [Diagnostics.Process]::Start($studioWindowInfo)
    $studioNewWindow.Dispose()
    exit
}
$studioData = Join-Path $studioRoot 'data'
$studioIdentity = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($studioData))
New-Item -ItemType Directory -Force -Path $studioData | Out-Null
$env:COMIC_STUDIO_DATA = $studioData
$studioPython = Join-Path $studioRoot 'runtime/python/python.exe'
$studioStartupLock = $null
$studioHasLock = $false
try {
    $studioHash = [Security.Cryptography.SHA256]::Create()
    try { $studioLockId = [BitConverter]::ToString($studioHash.ComputeHash([Text.Encoding]::UTF8.GetBytes($studioRoot.ToUpperInvariant()))).Replace('-','') } finally { $studioHash.Dispose() }
    $studioStartupLock = New-Object Threading.Mutex($false, "Local\AIComicStudioBackend_$studioLockId")
    try { $studioHasLock = $studioStartupLock.WaitOne(30000) } catch [Threading.AbandonedMutexException] { $studioHasLock = $true }
    if (-not $studioHasLock) { throw 'Another startup or restart is still in progress.' }
    if (-not (Test-Path -LiteralPath $studioPython)) { throw 'Bundled Python is missing. Extract the complete ZIP again.' }
    & $studioPython -c 'import fastapi,uvicorn,httpx,multipart,PIL' 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $studioPython -m pip install -r (Join-Path $studioRoot 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Please check your network.' }
    }
    $studioDesiredVersion = & $studioPython (Join-Path $studioRoot 'scripts/workbench_runtime.py') --fingerprint
    if ($LASTEXITCODE -ne 0 -or $studioDesiredVersion -notmatch '^[a-f0-9]{64}$') { throw 'Could not identify the current backend version.' }
    $studioPort = $null
    $existing = $false
    $studioCandidates = @(8766..8786)
    # Reuse the most recently started instance of this workspace first. During
    # an upgrade an older idle instance may still be listening on the first port.
    $studioStateFile = Join-Path $studioData 'server.json'
    if (Test-Path -LiteralPath $studioStateFile) {
        try {
            $studioSavedPort = [int]((Get-Content -LiteralPath $studioStateFile -Raw -Encoding UTF8 | ConvertFrom-Json).port)
            if ($studioSavedPort -ge 8766 -and $studioSavedPort -le 8786) {
                $studioCandidates = @($studioSavedPort) + @($studioCandidates | Where-Object { $_ -ne $studioSavedPort })
            }
        } catch {}
    }
    # Discover an existing workspace before choosing any free port.
    foreach ($candidate in $studioCandidates) {
        if (-not (Test-StudioListener $candidate)) { continue }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$candidate/api/health" -TimeoutSec 15
            if ($health.workspace_id -eq $studioIdentity) { $studioPort = $candidate; $existing = $true; break }
        } catch {}
    }
    if ($existing -and ($Restart -or $health.backend_fingerprint -ne $studioDesiredVersion)) {
        $studioWork = Get-StudioActivity
        if ($studioWork.busy) {
            if ($Restart) { throw 'Work is still running; backend was not restarted.' }
            Write-Output 'STUDIO_UPDATE_PENDING=active-work'
        } else {
            & (Join-Path $studioRoot '停止工作台.ps1')
            $studioStopped = $false
            foreach ($attempt in 1..40) {
                try { $studioOldHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$studioPort/api/health" -TimeoutSec 1 }
                catch { $studioStopped = $true; break }
                if ($studioOldHealth.workspace_id -ne $studioIdentity) { throw 'The local port changed ownership during restart.' }
                Start-Sleep -Milliseconds 250
            }
            if (-not $studioStopped) { throw 'The old backend is still running; no second backend was started.' }
            $studioCandidates = @($studioPort) + @($studioCandidates | Where-Object { $_ -ne $studioPort })
            $studioPort = $null
            $existing = $false
        }
    }
    if (-not $existing) { foreach ($candidate in $studioCandidates) {
        try {
            $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback,$candidate)
            $listener.Start(); $listener.Stop(); $studioPort = $candidate; break
        } catch {}
    } }
    if (-not $studioPort) { throw 'No available local port in 8766-8786.' }
    if (-not $existing) {
        $studioStartedPid = & $studioPython (Join-Path $studioRoot 'scripts/start_server.py') --port $studioPort
        if ($LASTEXITCODE -ne 0 -or $studioStartedPid -notmatch '^\d+$') { throw 'Could not start the detached backend; see data/server-error.log.' }
        $ready = $false
        foreach ($attempt in 1..40) {
            Start-Sleep -Milliseconds 250
            try { $health=Invoke-RestMethod -Uri "http://127.0.0.1:$studioPort/api/health" -TimeoutSec 1; if($health.workspace_id -eq $studioIdentity){$ready=$true;break} } catch {}
        }
        if (-not $ready) { throw 'Startup failed. See data/server-error.log for details.' }
    }
    # Record the actual listener PID, including when an existing instance is reused.
    $studioActualPid = $health.pid
    if (-not $studioActualPid) {
        $studioActualProcess = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.ExecutablePath -eq [IO.Path]::GetFullPath($studioPython) -and $_.CommandLine -match "uvicorn\s+app\.main:app\s+.*--port\s+$studioPort(?:\s|$)" })
        if ($studioActualProcess.Count -eq 1) { $studioActualPid = $studioActualProcess[0].ProcessId }
    }
    @{pid=$studioActualPid;port=$studioPort;python=$studioPython;backend_fingerprint=$health.backend_fingerprint;runtime_id=$health.runtime_id;workspace_id=$studioIdentity} | ConvertTo-Json | Set-Content -LiteralPath $studioStateFile -Encoding UTF8
    Write-Output "STUDIO_PORT=$studioPort"
} catch {
    $_ | Out-File -LiteralPath (Join-Path $studioData 'startup-error.log') -Encoding UTF8
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
} finally {
    if ($studioHasLock) { $studioStartupLock.ReleaseMutex() }
    if ($studioStartupLock) { $studioStartupLock.Dispose() }
}
