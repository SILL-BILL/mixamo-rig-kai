[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SessionLog,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [datetime]$SinceUtc = [datetime]::MinValue
)

$ErrorActionPreference = "Stop"
$records = [System.Collections.Generic.List[object]]::new()

Get-Content -LiteralPath $SessionLog | ForEach-Object {
    try {
        $entry = $_ | ConvertFrom-Json -Depth 30
    }
    catch {
        return
    }

    if ($entry.type -ne "event_msg" -or $entry.payload.item.type -ne "CommandExecution") {
        return
    }

    $timestamp = [datetime]$entry.timestamp
    if ($timestamp -lt $SinceUtc) { return }

    $command = [string]$entry.payload.item.command[-1]
    $blenderPattern = "(?i)&\s*'(?<exe>C:\\Program Files\\Blender Foundation\\Blender [^']+\\blender\.exe)'"
    $invocations = [regex]::Matches($command, $blenderPattern)
    if ($invocations.Count -eq 0) { return }

    $environment = [ordered]@{}
    foreach ($name in @(
        "BLENDER_USER_RESOURCES",
        "BLENDER_USER_CONFIG",
        "BLENDER_USER_SCRIPTS",
        "BLENDER_USER_DATAFILES",
        "TEMP",
        "TMP"
    )) {
        $pattern = "(?i)\`$env:$name\s*=\s*'([^']*)'"
        $match = [regex]::Match($command, $pattern)
        $environment[$name] = if ($match.Success) { $match.Groups[1].Value } else { $null }
    }

    $stdout = [string]$entry.payload.item.stdout
    $records.Add([pscustomobject]@{
        timestamp_utc = $timestamp.ToUniversalTime().ToString("o")
        cwd = [string]$entry.payload.item.cwd
        exit_code = $entry.payload.item.exit_code
        blender_invocation_count = $invocations.Count
        blender_executables = @($invocations | ForEach-Object { $_.Groups["exe"].Value })
        command = $command
        environment = $environment
        preferences_saved_reported = ($stdout -match "Preferences saved")
        repository_operation = ($command -match "(?i)extension repo-(add|remove|sync|list)")
        install_or_uninstall_operation = ($command -match "(?i)extension (install-file|uninstall)")
        clear_all = ($command -match "(?i)--clear-all")
        background = ($command -match "(?i)(--background|\s-b\s)")
        factory_startup = ($command -match "(?i)--factory-startup")
        python_scripts = @([regex]::Matches($command, "(?i)--python\s+'([^']+)'" ) | ForEach-Object { $_.Groups[1].Value })
        explicit_quit_reported = ($stdout -match "Blender quit")
    })
}

$result = [pscustomobject]@{
    schema_version = 1
    source_session_log = [System.IO.Path]::GetFullPath($SessionLog)
    since_utc = $SinceUtc.ToUniversalTime().ToString("o")
    extracted_at_utc = [DateTime]::UtcNow.ToString("o")
    shell_command_count = $records.Count
    blender_invocation_count = (($records | Measure-Object -Property blender_invocation_count -Sum).Sum)
    commands = @($records)
}

$parent = Split-Path -Parent ([System.IO.Path]::GetFullPath($OutputPath))
if ($parent -and -not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}
$result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Output "EXTRACT_OK commands=$($records.Count) invocations=$($result.blender_invocation_count) output=$OutputPath"
