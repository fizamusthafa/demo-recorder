param([string]$ScriptPath, [string]$Code, [string]$Mark)
# Runs a Playwright action against the dedicated window through the loopback controller
# and appends before/after OBS timecodes to .demo-recorder/timeline.jsonl for editing.
$ErrorActionPreference = 'Stop'
$home_ = if ($env:DEMO_RECORDER_HOME) { $env:DEMO_RECORDER_HOME } else { Join-Path (Get-Location) '.demo-recorder' }
$controlFile = Join-Path $home_ 'control.json'
if (-not (Test-Path $controlFile)) { throw 'Controller not running. Start: node browser.cjs serve' }
$control = Get-Content -Raw $controlFile | ConvertFrom-Json
$script = if ($Code) { $Code } else { Get-Content -Raw -LiteralPath $ScriptPath }
$label = if ($Mark) { $Mark } elseif ($ScriptPath) { [IO.Path]::GetFileNameWithoutExtension($ScriptPath) } else { 'inline' }
$obs = Join-Path $PSScriptRoot 'obs.py'
$timeline = Join-Path $home_ 'timeline.jsonl'

function Get-RecordState {
  try { python $obs GetRecordStatus 2>$null | ConvertFrom-Json } catch { $null }
}
function Write-Mark($phase) {
  @{ label = $label; phase = $phase; utc = [DateTime]::UtcNow.ToString('o'); recording = (Get-RecordState) } |
    ConvertTo-Json -Depth 5 -Compress | Add-Content $timeline
}

Write-Mark 'before'
$body = @{ script = $script } | ConvertTo-Json -Compress
$result = Invoke-RestMethod -Uri "http://127.0.0.1:$($control.port)" -Method Post `
  -Headers @{ Authorization = "Bearer $($control.token)" } `
  -Body ([Text.Encoding]::UTF8.GetBytes($body)) -ContentType 'application/json' -TimeoutSec 900
Write-Mark 'after'
$result | ConvertTo-Json -Depth 12
