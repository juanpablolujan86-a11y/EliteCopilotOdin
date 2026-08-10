#define MyAppName "ODIN"
#define MyAppVersion "0.7.2-beta"
#define MyAppPublisher "ODIN Project"
#define MyAppExeName "ODIN.exe"

[Setup]
AppId={{78C235AB-6443-4BA8-97E0-0D1A07010001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\ODIN
DefaultGroupName=ODIN
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=ODIN-v{#MyAppVersion}-Setup-win64
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: checkedonce
Name: "ollama"; Description: "Instalar Ollama y descargar gemma3:4b (requiere Internet y varios GB)"; GroupDescription: "Asistente local de inteligencia artificial:"; Flags: checkedonce

[Files]
Source: "..\dist\ODIN\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "setup_ollama.ps1"; DestDir: "{app}\tools"; Flags: ignoreversion

[Icons]
Name: "{group}\ODIN"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\ODIN"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\tools\setup_ollama.ps1"""; WorkingDir: "{app}"; StatusMsg: "Instalando Ollama y preparando gemma3:4b..."; Flags: waituntilterminated; Tasks: ollama
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar ODIN"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\tools"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := IsWin64;
  if not Result then
    MsgBox('ODIN requiere Windows de 64 bits.', mbError, MB_OK);
end;
