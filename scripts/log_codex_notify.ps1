param(
    [Parameter(Position = 0, Mandatory = $true)]
    [string]$NotificationJson
)

$ErrorActionPreference = "Stop"

function Get-GitValue {
    param(
        [string]$WorkingDirectory,
        [string[]]$Arguments
    )

    try {
        $value = (& git -C $WorkingDirectory @Arguments 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -eq 0) { return $value }
    } catch {
        # Notification logging must never interrupt Codex.
    }
    return ""
}

function Get-MessageText {
    param($Message)

    if ($null -eq $Message) { return "" }
    if ($Message -is [string]) { return $Message }

    foreach ($propertyName in @("text", "content", "message", "prompt")) {
        $property = $Message.PSObject.Properties[$propertyName]
        if ($property -and $property.Value -is [string]) {
            return [string]$property.Value
        }
    }
    return ""
}

try {
    $data = $NotificationJson | ConvertFrom-Json
    if ([string]$data.type -ne "agent-turn-complete") { exit 0 }

    $cwd = [string]$data.cwd
    if (-not $cwd -or -not (Test-Path -LiteralPath $cwd -PathType Container)) { exit 0 }

    $scriptRepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
    $eventRepoRoot = Get-GitValue -WorkingDirectory $cwd -Arguments @("rev-parse", "--show-toplevel")
    if (-not $eventRepoRoot) { exit 0 }
    $eventRepoRoot = [IO.Path]::GetFullPath($eventRepoRoot)
    $trimChars = [char[]]@(92, 47)
    if (-not [string]::Equals(
        $scriptRepoRoot.TrimEnd($trimChars),
        $eventRepoRoot.TrimEnd($trimChars),
        [StringComparison]::OrdinalIgnoreCase
    )) { exit 0 }

    $origin = Get-GitValue -WorkingDirectory $eventRepoRoot -Arguments @("remote", "get-url", "origin")
    if (-not $origin) { exit 0 }
    $repo = ($origin.TrimEnd("/") -split "/")[-1]
    if ($repo.EndsWith(".git")) { $repo = $repo.Substring(0, $repo.Length - 4) }

    $sessionId = [string]$data.'thread-id'
    $turnId = [string]$data.'turn-id'
    $branch = Get-GitValue -WorkingDirectory $eventRepoRoot -Arguments @("rev-parse", "--abbrev-ref", "HEAD")
    $commit = Get-GitValue -WorkingDirectory $eventRepoRoot -Arguments @("rev-parse", "--short", "HEAD")
    $student = Get-GitValue -WorkingDirectory $eventRepoRoot -Arguments @("config", "user.email")

    $configuredLogDir = [Environment]::GetEnvironmentVariable("AI_LOG_DIR")
    $logDir = if ($configuredLogDir) { $configuredLogDir } else { Join-Path $eventRepoRoot ".ai-log" }
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $logFile = Join-Path $logDir "session.jsonl"

    $existingKeys = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    $keySeparator = [char]31
    if (Test-Path -LiteralPath $logFile -PathType Leaf) {
        foreach ($line in (Get-Content -LiteralPath $logFile -Encoding UTF8 -Tail 500 -ErrorAction SilentlyContinue)) {
            try {
                $old = $line | ConvertFrom-Json
                if ([string]$old.tool -eq "codex" -and [string]$old.event -eq "UserPromptSubmit") {
                    $key = "{0}{3}{1}{3}{2}" -f [string]$old.session_id, [string]$old.turn_id, [string]$old.prompt, $keySeparator
                    [void]$existingKeys.Add($key)
                }
            } catch {
                # Ignore malformed historic lines; the next append is still valid JSONL.
            }
        }
    }

    foreach ($message in @($data.'input-messages')) {
        $prompt = Get-MessageText $message
        if (-not $prompt) { continue }
        if ($prompt.Length -gt 1000) { $prompt = $prompt.Substring(0, 1000) }

        $key = "{0}{3}{1}{3}{2}" -f $sessionId, $turnId, $prompt, $keySeparator
        if (-not $existingKeys.Add($key)) { continue }

        $entry = [ordered]@{
            ts = [DateTimeOffset]::Now.ToString("o")
            tool = "codex"
            event = "UserPromptSubmit"
            session_id = $sessionId
            model = ""
            repo = $repo
            branch = $branch
            commit = $commit
            student = $student
            prompt = $prompt
            turn_id = $turnId
            transcript_path = ""
            source = "notify"
        }
        $jsonLine = ($entry | ConvertTo-Json -Compress -Depth 8) + [Environment]::NewLine
        [IO.File]::AppendAllText($logFile, $jsonLine, [Text.UTF8Encoding]::new($false))
    }
} catch {
    # This is a best-effort audit log; failures must not break a Codex turn.
    if ([Environment]::GetEnvironmentVariable("AI_LOG_DEBUG")) {
        [Console]::Error.WriteLine("Codex notify logger: $($_.Exception.Message)")
    }
}

exit 0
