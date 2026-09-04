$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$spec = Join-Path $projectRoot "installer\ODIN.iss"
$pyInstaller = Join-Path $projectRoot ".venv\Scripts\pyinstaller.exe"
$pyInstallerSpec = Join-Path $projectRoot "ODIN.spec"

if (-not (Test-Path -LiteralPath $pyInstaller)) {
    throw "PyInstaller no está disponible en .venv. Prepare primero el entorno de desarrollo de ODIN."
}
if (-not (Test-Path -LiteralPath $pyInstallerSpec)) {
    throw "No se encontró ODIN.spec."
}

Write-Host "Construyendo ODIN.exe desde el código actual..."
Push-Location $projectRoot
try {
    & $pyInstaller --noconfirm --clean --distpath (Join-Path $projectRoot "dist\review-beta") --workpath (Join-Path $projectRoot "build\review-beta") $pyInstallerSpec
    if ($LASTEXITCODE -ne 0) { throw "La creación de ODIN.exe falló." }
}
finally {
    Pop-Location
}

$candidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 7\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe")
)
$compiler = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $compiler) {
    throw "Inno Setup no está instalado. Instálelo con: winget install JRSoftware.InnoSetup"
}
Write-Host "Construyendo el instalador de ODIN..."
& $compiler $spec
if ($LASTEXITCODE -ne 0) { throw "La creación del instalador falló." }

$installer = Join-Path $projectRoot "dist\installer\ODIN-v0.8.2-beta-Setup-win64.exe"
if (-not (Test-Path -LiteralPath $installer)) {
    throw "El compilador terminó sin generar el instalador esperado: $installer"
}
Get-Item -LiteralPath $installer | Select-Object FullName, Length, LastWriteTime
