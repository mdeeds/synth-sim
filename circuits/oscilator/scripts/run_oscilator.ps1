param(
    [string]$LtspiceExe = 'C:\Users\mdeed\AppData\Local\Programs\ADI\LTspice\LTspice.exe'
)

$ErrorActionPreference = 'Stop'
$circuitDir = Split-Path $PSScriptRoot -Parent
$simulationDir = Join-Path $circuitDir 'sim'
New-Item -ItemType Directory -Force -Path $simulationDir | Out-Null

if (-not (Test-Path -LiteralPath $LtspiceExe -PathType Leaf)) {
    throw "LTspice executable not found: $LtspiceExe"
}

$name = 'oscilator'
$circuit = Join-Path $circuitDir ($name + '.cir')
$raw = Join-Path $circuitDir ($name + '.raw')
$log = Join-Path $circuitDir ($name + '.log')
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
foreach ($extension in @('.op.raw', '.db')) {
    $generatedFile = Join-Path $circuitDir ($name + $extension)
    if (Test-Path -LiteralPath $generatedFile -PathType Leaf) {
        Move-Item -LiteralPath $generatedFile `
            -Destination (Join-Path $simulationDir ($name + $extension)) -Force
    }
}

python (Join-Path $PSScriptRoot 'plot_oscilator.py') `
    (Join-Path $simulationDir ($name + '.raw')) $simulationDir
if ($LASTEXITCODE -ne 0) {
    throw "Oscillator plot generation failed with exit code $LASTEXITCODE"
}
