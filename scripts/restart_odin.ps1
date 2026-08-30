$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..")).TrimEnd("\")
$expectedPython = [System.IO.Path]::GetFullPath((Join-Path $projectRoot ".venv\Scripts\python.exe"))
$expectedPythonw = [System.IO.Path]::GetFullPath((Join-Path $projectRoot ".venv\Scripts\pythonw.exe"))
$running = Get-CimInstance Win32_Process | Where-Object {
    $_.ExecutablePath -in @($expectedPython, $expectedPythonw)
}
$packaged = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "ODIN.exe" -and
    $_.ExecutablePath -and
    [System.IO.Path]::GetFullPath($_.ExecutablePath).StartsWith(
        $projectRoot + "\",
        [System.StringComparison]::OrdinalIgnoreCase
    )
}
$staleConsoles = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "powershell.exe" -and
    $_.CommandLine -like "*$projectRoot*" -and
    $_.CommandLine -like "*\.venv\Scripts\python.exe*" -and
    $_.CommandLine -like "*main.py*"
}
if ($running) {
    Stop-Process -Id @($running.ProcessId) -Force -ErrorAction SilentlyContinue
}
if ($packaged) {
    Stop-Process -Id @($packaged.ProcessId) -Force -ErrorAction SilentlyContinue
}
if ($staleConsoles) {
    Stop-Process -Id @($staleConsoles.ProcessId) -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1
Start-Process -FilePath $expectedPythonw -WorkingDirectory $projectRoot -ArgumentList @("main.py") -WindowStyle Hidden
Start-Sleep -Seconds 3
$active = Get-CimInstance Win32_Process | Where-Object {
    $_.ExecutablePath -in @($expectedPython, $expectedPythonw)
}
if (-not $active) { throw "ODIN no pudo iniciarse." }
$active | Select-Object ProcessId, ParentProcessId, CommandLine
