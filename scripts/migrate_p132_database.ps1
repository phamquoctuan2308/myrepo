[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^postgres(?:ql)?://")]
    [string]$TargetDatabaseUrl,

    [string]$BackupPath = (Join-Path (Get-Location) "orbit-p132.dump"),

    [switch]$SkipExport
)

$ErrorActionPreference = "Stop"
$backupFullPath = [System.IO.Path]::GetFullPath($BackupPath)
$backupDirectory = Split-Path -Parent $backupFullPath
$backupName = Split-Path -Leaf $backupFullPath
$containerDumpPath = "/tmp/orbit-p132.dump"

if (-not (Test-Path -LiteralPath $backupDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $backupDirectory | Out-Null
}

if (-not $SkipExport) {
    $postgresContainer = (docker compose ps -q postgres).Trim()
    if (-not $postgresContainer) {
        throw "The Docker Compose postgres service is not running. Start it before exporting P132."
    }

    docker compose exec -T postgres pg_dump --format=custom --no-owner --no-privileges `
        --file=$containerDumpPath --username=orbit --dbname=orbit
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed."
    }

    docker cp "${postgresContainer}:${containerDumpPath}" $backupFullPath
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to copy the database dump from the postgres container."
    }
    docker compose exec -T postgres rm -f $containerDumpPath
}

if (-not (Test-Path -LiteralPath $backupFullPath -PathType Leaf)) {
    throw "Database dump not found: $backupFullPath"
}

$targetUri = [System.Uri]$TargetDatabaseUrl
$safeTarget = "{0}/{1}" -f $targetUri.Host, $targetUri.AbsolutePath.TrimStart("/")
$operation = "back up the target, replace its public schema, and restore the P132 database"
if (-not $PSCmdlet.ShouldProcess($safeTarget, $operation)) {
    return
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$targetBackupName = "orbit-target-before-restore-$timestamp.dump"
$mount = "type=bind,source=$backupDirectory,target=/backup"

docker run --rm --mount $mount postgres:16-alpine `
    pg_dump --format=custom --no-owner --no-privileges `
    --file="/backup/$targetBackupName" $TargetDatabaseUrl
if ($LASTEXITCODE -ne 0) {
    throw "The safety backup of the target database failed; the target was not modified."
}

$resetSql = "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
$resetSql | docker run --rm --interactive postgres:16-alpine `
    psql --dbname=$TargetDatabaseUrl --set=ON_ERROR_STOP=1
if ($LASTEXITCODE -ne 0) {
    throw "Unable to reset the target public schema. Restore the safety backup if needed."
}

docker run --rm --mount $mount postgres:16-alpine `
    pg_restore --exit-on-error --no-owner --no-privileges `
    --dbname=$TargetDatabaseUrl "/backup/$backupName"
if ($LASTEXITCODE -ne 0) {
    throw "Restore failed. The pre-restore target backup is $targetBackupName."
}

Write-Host "P132 database restored successfully to $safeTarget."
Write-Host "Source dump: $backupFullPath"
Write-Host "Target safety backup: $(Join-Path $backupDirectory $targetBackupName)"
