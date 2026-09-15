[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Snapshot", "Compare", "RunIsolated")]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$SnapshotPath,

    [string]$ReportPath,

    [string[]]$Versions = @("4.2", "5.1"),

    [string]$NormalRoot = (Join-Path $env:APPDATA "Blender Foundation\Blender"),

    [string]$BlenderPath,

    [string]$IsolatedRoot,

    [string[]]$BlenderArguments = @()
)

$ErrorActionPreference = "Stop"

function Get-NormalProfileState {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string[]]$TargetVersions
    )

    $records = [System.Collections.Generic.List[object]]::new()
    foreach ($version in $TargetVersions) {
        $versionRoot = Join-Path $Root $version
        $candidates = [System.Collections.Generic.List[string]]::new()
        $userPref = Join-Path $versionRoot "config\userpref.blend"
        $candidates.Add($userPref)

        $configRoot = Join-Path $versionRoot "config"
        if (Test-Path -LiteralPath $configRoot) {
            Get-ChildItem -LiteralPath $configRoot -File -Recurse -Force |
                ForEach-Object { $candidates.Add($_.FullName) }
        }

        $extensionRoot = Join-Path $versionRoot "extensions"
        if (Test-Path -LiteralPath $extensionRoot) {
            Get-ChildItem -LiteralPath $extensionRoot -File -Recurse -Force |
                Where-Object {
                    $_.FullName -match "\\\.blender_ext\\" -or
                    $_.FullName -match "\\extensions\\\.cache\\"
                } |
                ForEach-Object { $candidates.Add($_.FullName) }
        }

        foreach ($path in ($candidates | Sort-Object -Unique)) {
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                $item = Get-Item -LiteralPath $path
                $records.Add([pscustomobject]@{
                    version = $version
                    path = $item.FullName
                    exists = $true
                    length = $item.Length
                    creation_time_utc = $item.CreationTimeUtc.ToString("o")
                    last_write_time_utc = $item.LastWriteTimeUtc.ToString("o")
                    sha256 = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash
                })
            }
            else {
                $records.Add([pscustomobject]@{
                    version = $version
                    path = [System.IO.Path]::GetFullPath($path)
                    exists = $false
                    length = $null
                    creation_time_utc = $null
                    last_write_time_utc = $null
                    sha256 = $null
                })
            }
        }
    }

    return [pscustomobject]@{
        schema_version = 1
        captured_at_utc = [DateTime]::UtcNow.ToString("o")
        normal_root = [System.IO.Path]::GetFullPath($Root)
        versions = $TargetVersions
        files = @($records)
    }
}

function Assert-OutputOutsideNormalProfile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Root
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $fullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    if ($fullPath.StartsWith($fullRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Audit output must not be written inside the normal Blender profile: $fullPath"
    }
}

function Compare-ProfileState {
    param(
        [Parameter(Mandatory = $true)]$Before,
        [Parameter(Mandatory = $true)]$After
    )

    $beforeMap = @{}
    foreach ($record in $Before.files) { $null = $beforeMap[$record.path] = $record }
    $afterMap = @{}
    foreach ($record in $After.files) { $null = $afterMap[$record.path] = $record }

    $changes = [System.Collections.Generic.List[object]]::new()
    foreach ($path in (($beforeMap.Keys + $afterMap.Keys) | Sort-Object -Unique)) {
        $old = $beforeMap[$path]
        $new = $afterMap[$path]
        $changed = $null -eq $old -or $null -eq $new
        if (-not $changed) {
            $oldWriteTime = if ($old.last_write_time_utc -is [datetime]) {
                $old.last_write_time_utc.ToUniversalTime().Ticks
            } elseif ($old.last_write_time_utc) {
                [DateTimeOffset]::Parse([string]$old.last_write_time_utc).UtcTicks
            } else { $null }
            $newWriteTime = if ($new.last_write_time_utc -is [datetime]) {
                $new.last_write_time_utc.ToUniversalTime().Ticks
            } elseif ($new.last_write_time_utc) {
                [DateTimeOffset]::Parse([string]$new.last_write_time_utc).UtcTicks
            } else { $null }
            $oldLength = if ($null -ne $old.length) { [long]$old.length } else { $null }
            $newLength = if ($null -ne $new.length) { [long]$new.length } else { $null }
            $oldSignature = "{0}|{1}|{2}|{3}" -f (
                [bool]$old.exists,
                $oldLength,
                $oldWriteTime,
                [string]$old.sha256
            )
            $newSignature = "{0}|{1}|{2}|{3}" -f (
                [bool]$new.exists,
                $newLength,
                $newWriteTime,
                [string]$new.sha256
            )
            $changed = $oldSignature -cne $newSignature
        }
        if ($changed) {
            $changes.Add([pscustomobject]@{
                path = $path
                before_signature = $oldSignature
                after_signature = $newSignature
                before = $old
                after = $new
            })
        }
    }
    return @($changes)
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$Path
    )

    Assert-OutputOutsideNormalProfile -Path $Path -Root $NormalRoot
    $parent = Split-Path -Parent ([System.IO.Path]::GetFullPath($Path))
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $Value | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $Path -Encoding utf8
}

if ($Mode -eq "Snapshot") {
    $snapshot = Get-NormalProfileState -Root $NormalRoot -TargetVersions $Versions
    Write-JsonFile -Value $snapshot -Path $SnapshotPath
    Write-Output "SNAPSHOT_OK $SnapshotPath"
    exit 0
}

if ($Mode -eq "Compare") {
    Assert-OutputOutsideNormalProfile -Path $SnapshotPath -Root $NormalRoot
    $before = Get-Content -LiteralPath $SnapshotPath -Raw | ConvertFrom-Json
    $after = Get-NormalProfileState -Root $NormalRoot -TargetVersions $Versions
    $changes = Compare-ProfileState -Before $before -After $after
    $result = [pscustomobject]@{
        schema_version = 1
        compared_at_utc = [DateTime]::UtcNow.ToString("o")
        unchanged = ($changes.Count -eq 0)
        changed_file_count = $changes.Count
        changes = $changes
    }
    if ($ReportPath) { Write-JsonFile -Value $result -Path $ReportPath }
    $result | ConvertTo-Json -Depth 12
    if ($changes.Count -ne 0) { exit 3 }
    exit 0
}

if (-not $BlenderPath -or -not $IsolatedRoot -or -not $ReportPath) {
    throw "RunIsolated requires -BlenderPath, -IsolatedRoot, and -ReportPath."
}

$normalFull = [System.IO.Path]::GetFullPath($NormalRoot).TrimEnd('\') + '\'
$isolatedFull = [System.IO.Path]::GetFullPath($IsolatedRoot).TrimEnd('\') + '\'
if ($isolatedFull.StartsWith($normalFull, [StringComparison]::OrdinalIgnoreCase)) {
    throw "IsolatedRoot must be outside the normal Blender profile: $isolatedFull"
}

Assert-OutputOutsideNormalProfile -Path $SnapshotPath -Root $NormalRoot
Assert-OutputOutsideNormalProfile -Path $ReportPath -Root $NormalRoot

foreach ($name in @("config", "scripts", "datafiles", "extensions", "temp")) {
    New-Item -ItemType Directory -Path (Join-Path $isolatedFull $name) -Force | Out-Null
}

$before = Get-NormalProfileState -Root $NormalRoot -TargetVersions $Versions
Write-JsonFile -Value $before -Path $SnapshotPath

$environmentNames = @(
    "BLENDER_USER_RESOURCES",
    "BLENDER_USER_CONFIG",
    "BLENDER_USER_SCRIPTS",
    "BLENDER_USER_DATAFILES",
    "TEMP",
    "TMP"
)
$savedEnvironment = @{}
foreach ($name in $environmentNames) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

$startedAt = [DateTime]::UtcNow
$exitCode = $null
$launchError = $null
try {
    $env:BLENDER_USER_RESOURCES = $isolatedFull.TrimEnd('\')
    $env:BLENDER_USER_CONFIG = Join-Path $isolatedFull "config"
    $env:BLENDER_USER_SCRIPTS = Join-Path $isolatedFull "scripts"
    $env:BLENDER_USER_DATAFILES = Join-Path $isolatedFull "datafiles"
    $env:TEMP = Join-Path $isolatedFull "temp"
    $env:TMP = Join-Path $isolatedFull "temp"

    & $BlenderPath @BlenderArguments
    $exitCode = $LASTEXITCODE
}
catch {
    $launchError = $_.Exception.Message
}
finally {
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], "Process")
    }
}

$after = Get-NormalProfileState -Root $NormalRoot -TargetVersions $Versions
$changes = Compare-ProfileState -Before $before -After $after
$runResult = [pscustomobject]@{
    schema_version = 1
    started_at_utc = $startedAt.ToString("o")
    finished_at_utc = [DateTime]::UtcNow.ToString("o")
    blender_path = [System.IO.Path]::GetFullPath($BlenderPath)
    blender_arguments = $BlenderArguments
    isolated_root = $isolatedFull.TrimEnd('\')
    environment = [ordered]@{
        BLENDER_USER_RESOURCES = $isolatedFull.TrimEnd('\')
        BLENDER_USER_CONFIG = Join-Path $isolatedFull "config"
        BLENDER_USER_SCRIPTS = Join-Path $isolatedFull "scripts"
        BLENDER_USER_DATAFILES = Join-Path $isolatedFull "datafiles"
        TEMP = Join-Path $isolatedFull "temp"
        TMP = Join-Path $isolatedFull "temp"
    }
    blender_exit_code = $exitCode
    launch_error = $launchError
    normal_profile_unchanged = ($changes.Count -eq 0)
    changed_file_count = $changes.Count
    changes = $changes
}
Write-JsonFile -Value $runResult -Path $ReportPath

if ($changes.Count -ne 0) {
    throw "NORMAL_BLENDER_PROFILE_CHANGED: $($changes.Count) monitored file(s)."
}
if ($launchError) { throw $launchError }
if ($exitCode -ne 0) { exit $exitCode }
Write-Output "ISOLATED_QA_OK $ReportPath"
