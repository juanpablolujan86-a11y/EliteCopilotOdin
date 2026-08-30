#define MyAppName "ODIN"
#define MyAppVersion "0.8.0-beta-pre-IA"
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
OutputDir=..\dist\public-pre-IA
OutputBaseFilename=ODIN-v{#MyAppVersion}-Setup-win64
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\assets\odin_raven.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: checkedonce

[Files]
Source: "..\dist\ODIN-public-pre-IA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ODIN"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\ODIN"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--set-language {code:GetOdinLanguage}"; WorkingDir: "{app}"; StatusMsg: "Configurando idioma y voces..."; Flags: runhidden waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar ODIN"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[Code]
var
  OdinLanguagePage: TInputOptionWizardPage;

procedure InitializeWizard();
begin
  OdinLanguagePage := CreateInputOptionPage(
    wpSelectTasks,
    'Idioma de ODIN',
    'Seleccione el idioma de la interfaz y de las voces',
    'Podrá cambiarlo posteriormente desde Configuración.',
    True,
    False
  );
  OdinLanguagePage.Add('Español latinoamericano');
  OdinLanguagePage.Add('Español (España)');
  OdinLanguagePage.Add('English (United States)');
  OdinLanguagePage.Add('English (United Kingdom)');
  OdinLanguagePage.Add('Português (Brasil)');
  OdinLanguagePage.SelectedValueIndex := 0;
end;

function GetOdinLanguage(Param: String): String;
begin
  case OdinLanguagePage.SelectedValueIndex of
    1: Result := 'es-ES';
    2: Result := 'en-US';
    3: Result := 'en-GB';
    4: Result := 'pt-BR';
  else
    Result := 'es-419';
  end;
end;

function InitializeSetup(): Boolean;
begin
  Result := IsWin64;
  if not Result then
    MsgBox('ODIN requiere Windows de 64 bits.', mbError, MB_OK);
end;
