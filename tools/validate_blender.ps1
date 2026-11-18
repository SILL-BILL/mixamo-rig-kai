param(
    [Parameter(Mandatory=$true)][string]$BlenderPath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateSet('full', 'safety', 'core')][string]$Suite = 'full',
    [string]$RunName = (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$testScripts = @{
    full = 'test_kai_facial.py'
    safety = 'test_kai_facial_safety.py'
    core = 'test_kai_core_compatibility.py'
}
$qaRoot = [IO.Path]::GetFullPath($OutputDirectory)
$normalUserRoot = Join-Path $env:APPDATA 'Blender Foundation\Blender'
if ($qaRoot.StartsWith($normalUserRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The validation output must be outside the normal Blender user directory.'
}
if ($RunName -notmatch '^[a-zA-Z0-9_.-]+$') { throw 'RunName must be a simple directory name.' }
$testUserDir = Join-Path $qaRoot ($RunName + '-' + $Suite)
$environmentNames = @(
    'KAI_QA_PROFILE', 'KAI_QA_SCRIPT', 'BLENDER_USER_RESOURCES',
    'BLENDER_USER_CONFIG', 'BLENDER_USER_SCRIPTS', 'BLENDER_USER_EXTENSIONS',
    'BLENDER_USER_DATAFILES', 'TEMP', 'TMP'
)
$savedEnvironment = @{}
foreach ($variableName in $environmentNames) {
    $savedEnvironment[$variableName] = [Environment]::GetEnvironmentVariable($variableName, 'Process')
}
try {
    $env:KAI_QA_PROFILE = $testUserDir
    $env:KAI_QA_SCRIPT = Join-Path $PSScriptRoot $testScripts[$Suite]
    $env:BLENDER_USER_RESOURCES = $testUserDir
    $env:BLENDER_USER_CONFIG = Join-Path $testUserDir 'config'
    $env:BLENDER_USER_SCRIPTS = Join-Path $testUserDir 'scripts'
    $env:BLENDER_USER_EXTENSIONS = Join-Path $testUserDir 'extensions'
    $env:BLENDER_USER_DATAFILES = Join-Path $testUserDir 'datafiles'
    $env:TEMP = Join-Path $testUserDir 'temp'
    $env:TMP = $env:TEMP
    New-Item -ItemType Directory -Path $env:BLENDER_USER_CONFIG,$env:BLENDER_USER_SCRIPTS,
        $env:BLENDER_USER_EXTENSIONS,$env:BLENDER_USER_DATAFILES,$env:TEMP -Force | Out-Null
    $logPath = Join-Path $testUserDir 'blender.log'
    & $BlenderPath --background --factory-startup --offline-mode --python-exit-code 1 --python (
        Join-Path $PSScriptRoot 'run_kai_facial_isolated.py'
    ) *> $logPath
    $blenderExitCode = $LASTEXITCODE
    Get-Content -LiteralPath $logPath -Tail 5
    if ($blenderExitCode -ne 0) { throw "Blender validation failed ($blenderExitCode): $logPath" }
    $resultPath = Join-Path $testUserDir 'run-result.json'
    $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
    if (-not $result.success) { throw "Validation did not succeed: $resultPath" }
    Write-Output "Validation result: $resultPath"
} finally {
    foreach ($variableName in $environmentNames) {
        [Environment]::SetEnvironmentVariable($variableName, $savedEnvironment[$variableName], 'Process')
    }
}
