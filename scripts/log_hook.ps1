param(
    [string]$Tool = "codex"
)

$ErrorActionPreference = "Stop"

function Get-GitValue {
    param([string[]]$Arguments)

    try {
        $value = (& git @Arguments 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -eq 0) { return $value }
    } catch {
        # Hooks must never block a Codex turn because metadata is unavailable.
    }
    return ""
}

try {
    $raw = [Console]::In.ReadToEnd().Trim()
    if (-not $raw) { exit 0 }
    $data = $raw | ConvertFrom-Json

    $event = if ($data.hook_event_name) { [string]$data.hook_event_name } else { [string]$data.event }
    $origin = Get-GitValue @("remote", "get-url", "origin")
    if (-not $origin) { exit 0 }

    $repo = ($origin.TrimEnd("/") -split "/")[-1]
    if ($repo.EndsWith(".git")) { $repo = $repo.Substring(0, $repo.Length - 4) }
    $repoRoot = Get-GitValue @("rev-parse", "--show-toplevel")
    $branch = Get-GitValue @("rev-parse", "--abbrev-ref", "HEAD")
    $commit = Get-GitValue @("rev-parse", "--short", "HEAD")
    $student = Get-GitValue @("config", "user.email")

    $prompt = if ($data.prompt) { [string]$data.prompt } else { "" }
    if ($prompt.Length -gt 1000) { $prompt = $prompt.Substring(0, 1000) }
    $sessionId = if ($data.session_id) { [string]$data.session_id } else { "" }
    $model = if ($data.model) { [string]$data.model } else { "" }
    $turnId = if ($data.turn_id) { [string]$data.turn_id } else { "" }
    $transcriptPath = if ($data.transcript_path) { [string]$data.transcript_path } else { "" }

    $hasPayload = $prompt -or ($event -in @("Stop", "stop", "SessionEnd", "sessionEnd", "AfterModel"))
    if (-not $hasPayload) { exit 0 }

    $entry = [ordered]@{
        ts = [DateTimeOffset]::Now.ToString("o")
        tool = $Tool.ToLowerInvariant()
        event = $event
        session_id = $sessionId
        model = $model
        repo = $repo
        branch = $branch
        commit = $commit
        student = $student
        prompt = $prompt
        turn_id = $turnId
        transcript_path = $transcriptPath
    }

    $configuredLogDir = [Environment]::GetEnvironmentVariable("AI_LOG_DIR")
    $logDir = if ($configuredLogDir) { $configuredLogDir } elseif ($repoRoot) { Join-Path $repoRoot ".ai-log" } else { ".ai-log" }
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $logFile = Join-Path $logDir "session.jsonl"
    $line = ($entry | ConvertTo-Json -Compress -Depth 5) + [Environment]::NewLine
    [IO.File]::AppendAllText($logFile, $line, [Text.UTF8Encoding]::new($false))
    Write-Output '{"continue":true}'
} catch {
    # Logging is best-effort and must never interrupt Codex.
    if ([Environment]::GetEnvironmentVariable("AI_LOG_DEBUG")) {
        [Console]::Error.WriteLine("Codex hook logger: $($_.Exception.Message)")
    }
}

exit 0
