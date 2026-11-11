param(
    [string]$LtspiceExe = 'C:\Users\mdeed\AppData\Local\Programs\ADI\LTspice\LTspice.exe'
)

$ErrorActionPreference = 'Stop'
$packageDir = Split-Path $PSScriptRoot -Parent
$simulationDir = Join-Path $packageDir 'sim'
$figure8Circuit = Join-Path $packageDir 'figure8.cir'
$figure8Raw = Join-Path $packageDir 'figure8.raw'
$figure8Log = Join-Path $packageDir 'figure8.log'
$figure10Circuit = Join-Path $simulationDir 'figure10.cir'
$figure10Raw = Join-Path $simulationDir 'figure10.raw'
$pythonScript = Join-Path $PSScriptRoot 'plot_figure8.py'

if (-not (Test-Path -LiteralPath $LtspiceExe -PathType Leaf)) {
    throw "LTspice executable not found: $LtspiceExe"
}

foreach ($circuit in @($figure8Circuit, $figure10Circuit)) {
    $process = Start-Process -FilePath $LtspiceExe `
        -ArgumentList @('-b', '-ascii', ('"{0}"' -f $circuit)) `
        -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "LTspice batch simulation failed for $circuit with exit code $($process.ExitCode)"
    }
}
foreach ($raw in @($figure8Raw, $figure10Raw)) {
    if (-not (Test-Path -LiteralPath $raw -PathType Leaf)) {
        throw "LTspice did not create the expected raw data file: $raw"
    }
}

$simulationFigure8Raw = Join-Path $simulationDir 'figure8.raw'
$simulationFigure8Log = Join-Path $simulationDir 'figure8.log'
Move-Item -LiteralPath $figure8Raw -Destination $simulationFigure8Raw -Force
if (Test-Path -LiteralPath $figure8Log -PathType Leaf) {
    Move-Item -LiteralPath $figure8Log -Destination $simulationFigure8Log -Force
}

python $pythonScript $simulationFigure8Raw $figure10Raw $packageDir
if ($LASTEXITCODE -ne 0) {
    throw "Figure plotting script failed with exit code $LASTEXITCODE"
}
