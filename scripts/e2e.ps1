$ErrorActionPreference = 'Stop'

$composeProject = "caliper-e2e-$PID-$([Guid]::NewGuid().ToString('N').Substring(0, 8))"
$random = [Security.Cryptography.RandomNumberGenerator]::Create()
$databasePasswordBytes = New-Object byte[] 32
$adminPasswordBytes = New-Object byte[] 32
$random.GetBytes($databasePasswordBytes)
$random.GetBytes($adminPasswordBytes)
$random.Dispose()
$env:POSTGRES_PASSWORD = [Convert]::ToBase64String($databasePasswordBytes)
$env:CALIPER_WEB_BIND = '127.0.0.1'
$env:CALIPER_WEB_PORT = '18443'
$env:CALIPER_SERVER_NAME = 'localhost'
$env:CALIPER_E2E_BASE_URL = 'https://localhost:18443'
$env:CALIPER_E2E_ADMIN_PASSWORD = [Convert]::ToBase64String($adminPasswordBytes)
$webPath = Join-Path $PSScriptRoot '..\web'

try {
    docker compose -p $composeProject up --build -d
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the isolated end-to-end stack.' }

    $deadline = (Get-Date).AddMinutes(3)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        try {
            docker compose -p $composeProject exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)" 2>$null | Out-Null
            $apiReady = $LASTEXITCODE -eq 0
            $webStatus = & curl.exe --ipv4 --insecure --silent --output NUL --write-out '%{http_code}' "$($env:CALIPER_E2E_BASE_URL)/"
            $ready = $apiReady -and $LASTEXITCODE -eq 0 -and $webStatus -eq '200'
        } catch { }
        if ($ready) { break }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw 'The isolated API did not become ready.' }

    docker compose -p $composeProject cp (Join-Path $PSScriptRoot 'e2e_seed_admin.py') api:/tmp/caliper-e2e-seed-admin.py
    if ($LASTEXITCODE -ne 0) { throw 'Could not copy the temporary administrator setup helper.' }
    $env:CALIPER_E2E_ADMIN_PASSWORD | docker compose -p $composeProject exec -T api python /tmp/caliper-e2e-seed-admin.py
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the temporary end-to-end administrator.' }

    Push-Location $webPath
    try {
        pnpm.cmd run test:e2e
        if ($LASTEXITCODE -ne 0) { throw 'The browser end-to-end test failed.' }
    } finally { Pop-Location }
} finally {
    docker compose -p $composeProject down -v
    Remove-Item Env:POSTGRES_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:CALIPER_WEB_BIND -ErrorAction SilentlyContinue
    Remove-Item Env:CALIPER_WEB_PORT -ErrorAction SilentlyContinue
    Remove-Item Env:CALIPER_SERVER_NAME -ErrorAction SilentlyContinue
    Remove-Item Env:CALIPER_E2E_BASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:CALIPER_E2E_ADMIN_PASSWORD -ErrorAction SilentlyContinue
}
