; IGI Tools — Inno Setup installer
; Builds an EXE that installs IGITools.bundle into Autodesk ApplicationPlugins.
;
; Prerequisites / one-shot build:
;   .\scripts\build-installer.ps1
; Or manually:
;   1. Run scripts\build-bundle.ps1 so that dist\IGITools.bundle exists
;   2. Compile this script with Inno Setup 6+ (ISCC.exe)

#define MyAppName "IGI Tools for AutoCAD"
; Prefer /DMyAppVersion=… from build-installer.ps1 (CLI define must not be overwritten).
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppPublisher "IGI"
#define MyAppURL "https://igi.ru/"
#define MyBundleName "IGITools.bundle"

[Setup]
AppId={{E1333436-1EF7-43B6-AE8C-B9B646519E6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={code:GetBundlePath}
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=IGITools-setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
WizardStyle=modern
UninstallDisplayName={#MyAppName}
InfoAfterFile=

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Assembled bundle produced by scripts\build-bundle.ps1
Source: "..\dist\IGITools.bundle\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs

[Icons]
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

[Code]
function GetBundlePath(Param: string): string;
begin
  Result := ExpandConstant('{commonpf64}') + '\Autodesk\ApplicationPlugins\{#MyBundleName}';
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    MsgBox(
      'IGI Tools установлен в:' + #13#10 +
      ExpandConstant('{app}') + #13#10 + #13#10 +
      'Перезапустите AutoCAD / Civil 3D.',
      mbInformation, MB_OK);
  end;
end;
