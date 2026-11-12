; MasterForge AI - official local desktop packaging recipe
; Builds a per-user Windows Setup EXE from the already-tested portable app.
; This installer is NOT Authenticode-signed by default.

#define MyAppName "MasterForge AI"
#define MyAppVersion "0.9.2"
#define MyAppExeName "MasterForge-AI.exe"

[Setup]
AppId={{C8FCA5E5-9913-5D3E-B4B8-9E88DB09D8A4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=MasterForge AI
DefaultDirName={localappdata}\Programs\MasterForge AI
DefaultGroupName=MasterForge AI
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
WizardStyle=modern
OutputDir=..\dist
OutputBaseFilename=MasterForge-AI-Setup-0.9.2
SetupIconFile=..\masterforge_python\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName=MasterForge AI
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
MinVersion=10.0
ArchitecturesAllowed=x64compatible
VersionInfoVersion=0.9.2.0
VersionInfoDescription=MasterForge AI desktop installer
VersionInfoProductName=MasterForge AI
VersionInfoProductVersion=0.9.2.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\MasterForge-AI.exe"; DestDir: "{app}"; DestName: "MasterForge-AI.exe"; Flags: ignoreversion
Source: "..\INSTALLATION-AND-PRIVACY.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\MasterForge AI"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\MasterForge AI"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch MasterForge AI"; Flags: nowait postinstall skipifsilent
