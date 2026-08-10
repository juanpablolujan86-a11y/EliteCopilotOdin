$ErrorActionPreference = "Stop"

$model = "gemma3:4b"
$ollama = Get-Command ollama.exe -ErrorAction SilentlyContinue
if (-not $ollama) {
    $knownPath = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path -LiteralPath $knownPath) {
        $ollama = Get-Item -LiteralPath $knownPath
    }
}

if (-not $ollama) {
    Write-Host "Descargando Ollama desde el sitio oficial..."
    $installer = Join-Path $env:TEMP "ODIN-OllamaSetup.exe"
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $installer
    Start-Process -FilePath $installer -ArgumentList "/SILENT" -Wait
    Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
    $knownPath = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (-not (Test-Path -LiteralPath $knownPath)) {
        throw "Ollama no pudo instalarse. ODIN igualmente quedó instalado."
    }
    $ollama = Get-Item -LiteralPath $knownPath
}

Write-Host "Preparando el modelo $model. La descarga puede tardar varios minutos..."
& $ollama.FullName pull $model
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo descargar el modelo $model. Puede reintentarlo con: ollama pull $model"
}
Write-Host "Ollama y $model quedaron listos para ODIN."
