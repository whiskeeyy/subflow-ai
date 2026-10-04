; =====================================================================
; SubFlow AI Studio - Inno Setup Packaging Script
; Produces a standalone, professional Windows 64-bit installer (.exe)
; =====================================================================

#define MyAppName "SubFlow AI"
#define MyAppVersion "2.0"
#define MyAppPublisher "SubFlow AI Studio"
#define MyAppURL "https://github.com/whiskeeyy/subflow-ai"
#define MyAppExeName "SubFlowAI.exe"

[Setup]
AppId={{C8E19280-9943-4DF6-8BC9-7F32D065D3C1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=dist_installer
OutputBaseFilename=SubFlowAI_Setup_v2.0
SetupIconFile=frontend\assets\logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\SubFlowAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Khởi chạy SubFlow AI ngay bây giờ"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up any temporary files or cache generated during runtime inside app folder
Type: filesandordirs; Name: "{app}\*"
; NOTE: User settings and downloaded AI models in %APPDATA%\SubFlowAI are preserved across reinstalls/uninstalls.
