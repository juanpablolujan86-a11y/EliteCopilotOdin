$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$pyInstaller = Join-Path $projectRoot ".venv\Scripts\pyinstaller.exe"
$pyInstallerSpec = Join-Path $projectRoot "ODIN-public-pre-IA.spec"
$innoSpec = Join-Path $projectRoot "installer\ODIN-public-pre-IA.iss"

if (-not (Test-Path -LiteralPath $pyInstaller)) {
    throw "PyInstaller no está disponible en .venv."
}

Push-Location $projectRoot
try {
    & $pyInstaller --noconfirm --clean $pyInstallerSpec
    if ($LASTEXITCODE -ne 0) { throw "La creación de ODIN público falló." }
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
if (-not $compiler) { throw "Inno Setup no está instalado." }

& $compiler $innoSpec
if ($LASTEXITCODE -ne 0) { throw "La creación del instalador público falló." }

$installer = Join-Path $projectRoot "dist\public-pre-IA\ODIN-v0.8.0-beta-pre-IA-Setup-win64.exe"
if (-not (Test-Path -LiteralPath $installer)) {
    throw "No se generó el instalador esperado: $installer"
}
$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $installer
$hashFile = "$installer.sha256.txt"
Set-Content -LiteralPath $hashFile -Value ("{0}  {1}" -f $hash.Hash, (Split-Path $installer -Leaf)) -Encoding ascii
Get-Item -LiteralPath $installer, $hashFile | Select-Object FullName, Length, LastWriteTime
