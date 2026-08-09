$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..")).TrimEnd("\")
$expectedPython = [System.IO.Path]::GetFullPath((Join-Path $projectRoot ".venv\Scripts\python.exe"))
$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and $_.CommandLine -match "main\.py" -and
    ($_.ExecutablePath -eq $expectedPython -or $_.CommandLine -like "*$projectRoot*")
}
$staleConsoles = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "powershell.exe" -and
    $_.CommandLine -like "*\.venv\Scripts\python.exe*" -and
    $_.CommandLine -like "*main.py*"
}
if ($running) {
    Stop-Process -Id @($running.ProcessId) -Force -ErrorAction SilentlyContinue
}
if ($staleConsoles) {
    Stop-Process -Id @($staleConsoles.ProcessId) -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1
Start-Process -FilePath "powershell.exe" -WorkingDirectory $projectRoot -ArgumentList @("-NoExit", "-Command", "& '.\.venv\Scripts\python.exe' '.\main.py'")
Start-Sleep -Seconds 3
$active = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and $_.CommandLine -match "main\.py" -and
    $_.CommandLine -like "*$projectRoot*"
}
if (-not $active) { throw "ODIN no pudo iniciarse." }
$active | Select-Object ProcessId, ParentProcessId, CommandLine
