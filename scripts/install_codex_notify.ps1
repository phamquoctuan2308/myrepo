param(
    [string]$ConfigPath = (Join-Path $env:USERPROFILE ".codex\config.toml"),
    [string]$NotifyScriptPath = (Join-Path $PSScriptRoot "log_codex_notify.ps1")
)

$ErrorActionPreference = "Stop"

$ConfigPath = [IO.Path]::GetFullPath($ConfigPath)
$NotifyScriptPath = [IO.Path]::GetFullPath($NotifyScriptPath)
if (-not (Test-Path -LiteralPath $NotifyScriptPath -PathType Leaf)) {
    throw "Codex notify logger was not found: $NotifyScriptPath"
}

$configDirectory = Split-Path -Parent $ConfigPath
New-Item -ItemType Directory -Path $configDirectory -Force | Out-Null
$content = if (Test-Path -LiteralPath $ConfigPath -PathType Leaf) {
    [IO.File]::ReadAllText($ConfigPath)
} else {
    ""
}

$backupPath = "$ConfigPath.ai-log.bak"
if (Test-Path -LiteralPath $ConfigPath -PathType Leaf) {
    [IO.File]::Copy($ConfigPath, $backupPath, $true)
}

$escapedScriptPath = $NotifyScriptPath.Replace("\", "\\").Replace('"', '\"')
$notifyLine = 'notify = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "' + $escapedScriptPath + '"]'
$newline = if ($content.Contains("`r`n")) { "`r`n" } else { "`n" }

$firstTable = [regex]::Match($content, '(?m)^\s*\[')
$headerLength = if ($firstTable.Success) { $firstTable.Index } else { $content.Length }
$header = $content.Substring(0, $headerLength)
$tables = $content.Substring($headerLength)

if ($header -match '(?m)^\s*notify\s*=.*$') {
    $header = [regex]::Replace($header, '(?m)^\s*notify\s*=.*$', $notifyLine, 1)
} else {
    $header = $notifyLine + $newline + $header
}

$updated = $header + $tables
[IO.File]::WriteAllText($ConfigPath, $updated, [Text.UTF8Encoding]::new($false))
Write-Output "Installed Codex notify logger in $ConfigPath"
