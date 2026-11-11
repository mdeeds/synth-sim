param(
    [string]$LtspiceExe = 'C:\Users\mdeed\AppData\Local\Programs\ADI\LTspice\LTspice.exe'
)

$ErrorActionPreference = 'Stop'
$packageDir = Split-Path $PSScriptRoot -Parent
$simulationDir = Join-Path $packageDir 'sim'
New-Item -ItemType Directory -Force -Path $simulationDir | Out-Null
$circuit = Join-Path $packageDir 'vca_transfer.cir'
$raw = Join-Path $packageDir 'vca_transfer.raw'
$log = Join-Path $packageDir 'vca_transfer.log'
$simulationRaw = Join-Path $simulationDir 'vca_transfer.raw'
$simulationLog = Join-Path $simulationDir 'vca_transfer.log'
$plotScript = Join-Path $PSScriptRoot 'plot_transfer.py'

if (-not (Test-Path -LiteralPath $LtspiceExe -PathType Leaf)) {
    throw "LTspice executable not found: $LtspiceExe"
}

$process = Start-Process -FilePath $LtspiceExe `
    -ArgumentList @('-b', '-ascii', ('"{0}"' -f $circuit)) `
    -Wait -PassThru
if ($process.ExitCode -ne 0) {
    throw "LTspice transfer simulation failed with exit code $($process.ExitCode)"
}
if (-not (Test-Path -LiteralPath $raw -PathType Leaf)) {
    throw "LTspice did not create the expected raw data file: $raw"
}

Move-Item -LiteralPath $raw -Destination $simulationRaw -Force
if (Test-Path -LiteralPath $log -PathType Leaf) {
    Move-Item -LiteralPath $log -Destination $simulationLog -Force
}

python (Join-Path $PSScriptRoot 'plot_transfer.py') $simulationRaw $packageDir
if ($LASTEXITCODE -ne 0) {
    throw "Transfer plot generation failed with exit code $LASTEXITCODE"
}
