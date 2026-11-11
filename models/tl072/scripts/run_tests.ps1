param(
    [string]$LtspiceExe = 'C:\Users\mdeed\AppData\Local\Programs\ADI\LTspice\LTspice.exe'
)

$ErrorActionPreference = 'Stop'
$packageDir = Split-Path $PSScriptRoot -Parent
$testDir = Join-Path $packageDir 'test'
$simulationDir = Join-Path $packageDir 'sim'
New-Item -ItemType Directory -Force -Path $simulationDir | Out-Null

if (-not (Test-Path -LiteralPath $LtspiceExe -PathType Leaf)) {
    throw "LTspice executable not found: $LtspiceExe"
}

foreach ($name in @('tl072_ac', 'tl072_transient')) {
    $circuit = Join-Path $testDir ($name + '.cir')
    $raw = Join-Path $testDir ($name + '.raw')
    $log = Join-Path $testDir ($name + '.log')
    $process = Start-Process -FilePath $LtspiceExe `
        -ArgumentList @('-b', '-ascii', ('"{0}"' -f $circuit)) `
        -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "LTspice simulation failed for $circuit with exit code $($process.ExitCode)"
    }
    if (-not (Test-Path -LiteralPath $raw -PathType Leaf)) {
        throw "LTspice did not create the expected raw data file: $raw"
    }
    Move-Item -LiteralPath $raw -Destination (Join-Path $simulationDir ($name + '.raw')) -Force
    if (Test-Path -LiteralPath $log -PathType Leaf) {
        Move-Item -LiteralPath $log -Destination (Join-Path $simulationDir ($name + '.log')) -Force
    }
    $operatingPointRaw = Join-Path $testDir ($name + '.op.raw')
    if (Test-Path -LiteralPath $operatingPointRaw -PathType Leaf) {
        Move-Item -LiteralPath $operatingPointRaw `
            -Destination (Join-Path $simulationDir ($name + '.op.raw')) -Force
    }
}

python (Join-Path $PSScriptRoot 'check_tests.py') $simulationDir
if ($LASTEXITCODE -ne 0) {
    throw "TL072 simulation checks failed with exit code $LASTEXITCODE"
}
