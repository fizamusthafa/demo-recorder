param(
  [int]$Port = $(if ($env:DEMO_CDP_PORT) { [int]$env:DEMO_CDP_PORT } else { 9333 }),
  [string]$ProfileDir = $(if ($env:DEMO_EDGE_PROFILE) { $env:DEMO_EDGE_PROFILE } else { Join-Path $env:LOCALAPPDATA 'demo-recorder\edge-profile' }),
  [string]$Url = 'https://www.office.com'
)
$ErrorActionPreference = 'Stop'

try {
  $existing = Invoke-RestMethod "http://127.0.0.1:$Port/json/version" -TimeoutSec 2
  Write-Output "Browser already listening on 127.0.0.1:$Port ($($existing.Browser))."
  return
} catch {}

$edge = @(
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "$env:LOCALAPPDATA\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $edge) { throw 'Microsoft Edge was not found.' }

New-Item -ItemType Directory -Force $ProfileDir | Out-Null
# A dedicated profile keeps the debugging port away from your everyday browser profile.
$edgeArgs = @(
  "--remote-debugging-port=$Port",
  "--remote-debugging-address=127.0.0.1",
  "--user-data-dir=`"$ProfileDir`"",
  '--no-first-run',
  '--no-default-browser-check',
  '--window-size=1920,1080',
  '--window-position=0,0',
  $Url
)
Start-Process -FilePath $edge -ArgumentList $edgeArgs | Out-Null

for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Milliseconds 500
  try {
    $v = Invoke-RestMethod "http://127.0.0.1:$Port/json/version" -TimeoutSec 2
    Write-Output "Edge ready on 127.0.0.1:$Port with profile $ProfileDir ($($v.Browser))."
    Write-Output 'Sign in manually in this window. The profile keeps you signed in for the next session.'
    return
  } catch {}
}
throw "Edge started but the debugging port $Port did not respond. Close other Edge windows that use the same profile and retry."
