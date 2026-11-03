param(
    [string]$DeviceId = '',
    [string]$ApkPath = '',
    [switch]$SkipInstall
)

# Run again after reconnecting the USB cable. Existing healthy services are reused.
$ErrorActionPreference = 'Stop'
$repoPath = Split-Path -Parent $PSScriptRoot
$runtimePath = Join-Path $repoPath 'backend\data\demo-runtime'
New-Item -ItemType Directory -Force -Path $runtimePath | Out-Null
$pythonCandidates = @(
    (Join-Path $repoPath 'backend\.venv\Scripts\python.exe'),
    (Join-Path $repoPath 'lab3\data-pipeline\.venv\Scripts\python.exe')
)
$pythonPath = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $pythonPath) { throw 'Set up the backend Python environment first; see backend/README.md.' }
if (-not (Test-Path -LiteralPath (Join-Path $repoPath 'backend\.env'))) {
    throw 'The private backend/.env is missing. Configure it on the laptop, not in the APK.'
}

function Get-LocalHealth([int]$Port) {
    try { return Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2 }
    catch { return $null }
}

function Start-LocalService([string]$Name, [int]$Port, [string]$Module, [string]$Directory) {
    $health = Get-LocalHealth $Port
    if ($null -ne $health) { return $health }
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($listener) { throw "Port $Port is occupied but its health check failed. Inspect that process before retrying." }
    $serviceProcess = Start-Process -FilePath $pythonPath `
        -ArgumentList @('-m', 'uvicorn', $Module, '--host', '127.0.0.1', '--port', "$Port", '--no-access-log') `
        -WorkingDirectory (Join-Path $repoPath $Directory) -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtimePath "$Name.stdout.log") `
        -RedirectStandardError (Join-Path $runtimePath "$Name.stderr.log")
    Set-Content -LiteralPath (Join-Path $runtimePath "$Name.pid") -Value $serviceProcess.Id
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        $serviceProcess.Refresh()
        if ($serviceProcess.HasExited) { throw "$Name stopped. Inspect backend/data/demo-runtime/$Name.stderr.log privately." }
        $health = Get-LocalHealth $Port
        if ($null -ne $health) { return $health }
        Start-Sleep -Milliseconds 500
    }
    throw "$Name startup timed out. Inspect backend/data/demo-runtime/$Name.stderr.log privately."
}

$modelHealth = Start-LocalService 'model' 8001 'service.main:app' 'ml'
if ($modelHealth.artifacts_loaded -ne $true) { throw 'The prediction model artifacts did not load.' }
$apiHealth = Start-LocalService 'api' 8000 'app:app' 'backend'
if ($apiHealth.status -ne 'ok' -or $apiHealth.prediction_configured -ne $true -or $apiHealth.prediction_output -ne 'probability') {
    throw 'Backend health is incomplete. Check PARKCHOICE_MODEL_URL=http://127.0.0.1:8001 in backend/.env.'
}
Write-Host "Backend ready; model $($modelHealth.model_version) loaded."
try {
    $search = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/destinations' `
        -ContentType 'application/json' -Body '{"query":"City Hall MRT"}' -TimeoutSec 30
    if ($search.status -ne 'ok' -or @($search.matches).Count -eq 0) { throw 'No usable matches' }
} catch { throw 'Live destination search failed. Check laptop internet and OneMap configuration before the demo.' }
Write-Host "Live destination search passed: $(@($search.matches).Count) matches."

$sdkCandidates = @($env:ANDROID_HOME, $env:ANDROID_SDK_ROOT, (Join-Path $env:LOCALAPPDATA 'Android\Sdk'))
$adbPath = $sdkCandidates | Where-Object { $_ } | ForEach-Object { Join-Path $_ 'platform-tools\adb.exe' } |
    Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $adbPath) { throw 'Android SDK platform-tools/adb.exe was not found.' }
$deviceOutput = @(& $adbPath devices -l)
if ($LASTEXITCODE -ne 0) { throw 'ADB could not list devices.' }
$devices = @($deviceOutput | ForEach-Object { if ($_ -match '^(\S+)\s+device\b') { $Matches[1] } })
if (-not $DeviceId) {
    if ($devices.Count -eq 0) {
        Write-Host 'Services are ready. Connect and unlock the phone, enable USB debugging, accept its prompt, then rerun this script.'
        if ($deviceOutput -match '\sunauthorized\b') { Write-Host 'A connected device still needs its USB debugging prompt accepted.' }
        return
    }
    if ($devices.Count -gt 1) {
        Write-Host ($deviceOutput -join "`n")
        throw 'More than one Android device is connected. Rerun with -DeviceId SERIAL to choose the demo phone.'
    }
    $DeviceId = $devices[0]
}
if ($DeviceId -notin $devices) { throw 'The selected device is not connected and authorized. Run adb devices -l.' }
& $adbPath -s $DeviceId reverse tcp:8000 tcp:8000
if ($LASTEXITCODE -ne 0) { throw 'USB port forwarding failed.' }

if (-not $SkipInstall) {
    if (-not $ApkPath) { $ApkPath = Join-Path $repoPath 'parkchoice_flutter\build\app\outputs\flutter-apk\app-debug.apk' }
    if (-not (Test-Path -LiteralPath $ApkPath)) { throw 'The demo APK is missing. Use -ApkPath to select a supplied APK, or -SkipInstall if this phone already has the current app.' }
    $ApkPath = (Resolve-Path -LiteralPath $ApkPath).Path
    & $adbPath -s $DeviceId install -r $ApkPath
    if ($LASTEXITCODE -ne 0) { throw 'APK installation failed. Existing phone data was not erased; inspect the ADB error.' }
}
& $adbPath -s $DeviceId shell am start -n 'com.example.parkchoicesg_2/.MainActivity'
if ($LASTEXITCODE -ne 0) { throw 'The installed app could not be launched.' }
Write-Host "App launched on $DeviceId with USB forwarding. Keep the laptop awake and the cable connected."
Write-Host 'First test: manually select an origin and destination, then Find carparks. Test GPS, map and navigation on the actual phone.'
Write-Host 'The phone needs internet for map tiles/navigation; the laptop needs internet for OneMap, the database and model feed.'
