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

[CustomMessages]
russian.UpdateTemplateTask=Обновить активный шаблон DWG (template.dwg) из дистрибутива
english.UpdateTemplateTask=Update the active DWG template (template.dwg) from the package

[Tasks]
; Показывается только если template.dwg уже есть. По умолчанию включено
; (в [Tasks] нет флага checked — задача checked по умолчанию; unchecked/checkedonce).
Name: updatetemplate; Description: "{cm:UpdateTemplateTask}"; \
  Check: ExistingTemplateExists

[Files]
; Assembled bundle produced by scripts\build-bundle.ps1.
; template.dwg — активный шаблон: при обновлении только по задаче.
; template.default.dwg — заводской эталон: всегда обновляется с дистрибутивом
;   (из него IGI_RESET_TEMPLATE восстанавливает template.dwg).
Source: "..\dist\IGITools.bundle\*"; DestDir: "{app}"; Excludes: "Contents\Resources\template.dwg"; Flags: recursesubdirs ignoreversion createallsubdirs
Source: "..\dist\IGITools.bundle\Contents\Resources\template.dwg"; DestDir: "{app}\Contents\Resources"; Flags: ignoreversion; Check: ShouldInstallTemplate

[Icons]
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

[Code]
const
  MinSupportedYear = 2022;
  MaxSupportedYear = 2027;

var
  VersionCheckPage: TWizardPage;
  VersionSummaryLabel: TNewStaticText;
  VersionMemo: TMemo;
  ConfirmCheckBox: TCheckBox;
  VersionNames: array of string;
  VersionYears: array of Integer;
  VersionSupported: array of Boolean;
  VersionCount: Integer;

{-- Registry helpers ------------------------------------------------------}

function ExtractYearFromProductName(const ProductName: string): Integer;
var
  I: Integer;
  YearStr: string;
begin
  Result := 0;
  for I := 1 to Length(ProductName) - 3 do
  begin
    YearStr := Copy(ProductName, I, 4);
    Result := StrToIntDef(YearStr, 0);
    if (Result >= 2000) and (Result <= 2100) then
      Exit;
  end;
  Result := 0;
end;

procedure ScanRelease(const RootKey, Release: string);
var
  SubKeys: TArrayOfString;
  J: Integer;
  ProductName: string;
  Year: Integer;
  FullPath: string;
begin
  FullPath := RootKey + '\' + Release;
  if not RegGetSubkeyNames(HKLM, FullPath, SubKeys) then Exit;

  for J := 0 to GetArrayLength(SubKeys) - 1 do
  begin
    if RegQueryStringValue(HKLM,
      FullPath + '\' + SubKeys[J],
      'ProductName', ProductName) then
    begin
      if (Pos('AutoCAD', ProductName) > 0) or (Pos('Civil', ProductName) > 0) then
      begin
        Year := ExtractYearFromProductName(ProductName);

        SetArrayLength(VersionNames, VersionCount + 1);
        SetArrayLength(VersionYears, VersionCount + 1);
        SetArrayLength(VersionSupported, VersionCount + 1);
        VersionNames[VersionCount] := ProductName;
        VersionYears[VersionCount] := Year;
        VersionSupported[VersionCount] :=
          (Year >= MinSupportedYear) and (Year <= MaxSupportedYear);
        VersionCount := VersionCount + 1;
      end;
    end;
  end;
end;

function CollectVersions: Boolean;
var
  RootKeys: array of string;
  RK: Integer;
  Releases: TArrayOfString;
  I: Integer;
begin
  SetArrayLength(RootKeys, 4);
  RootKeys[0] := 'SOFTWARE\Autodesk\AutoCAD';
  RootKeys[1] := 'SOFTWARE\WOW6432Node\Autodesk\AutoCAD';
  RootKeys[2] := 'SOFTWARE\Autodesk\Civil 3D';
  RootKeys[3] := 'SOFTWARE\WOW6432Node\Autodesk\Civil 3D';

  VersionCount := 0;
  SetArrayLength(VersionNames, 0);
  SetArrayLength(VersionYears, 0);
  SetArrayLength(VersionSupported, 0);

  for RK := 0 to GetArrayLength(RootKeys) - 1 do
  begin
    if not RegGetSubkeyNames(HKLM, RootKeys[RK], Releases) then Continue;

    for I := 0 to GetArrayLength(Releases) - 1 do
    begin
      if Copy(Releases[I], 1, 1) <> 'R' then Continue;
      ScanRelease(RootKeys[RK], Releases[I]);
    end;
  end;

  Result := VersionCount > 0;
end;

function GetCompatibleCount: Integer;
var
  I: Integer;
begin
  Result := 0;
  for I := 0 to VersionCount - 1 do
    if VersionSupported[I] then
      Result := Result + 1;
end;

{-- Custom page population ------------------------------------------------}

function FormatVersionList: string;
var
  I: Integer;
  Tick, Cross: string;
begin
  Result := '';
  Tick := '[+] ';
  Cross := '[-] ';

  for I := 0 to VersionCount - 1 do
  begin
    if VersionSupported[I] then
      Result := Result + Tick + VersionNames[I] + '    поддерживается'
    else
      Result := Result + Cross + VersionNames[I] + '    НЕ поддерживается';
    if I < VersionCount - 1 then
      Result := Result + #13#10;
  end;
end;

procedure PopulateVersionCheckPage;
var
  Compatible, Incompatible: Integer;
  Summary: string;
begin
  if VersionMemo = nil then Exit;

  Compatible := GetCompatibleCount;
  Incompatible := VersionCount - Compatible;

  VersionMemo.Text := FormatVersionList;

  if Incompatible = 0 then
  begin
    Summary :=
      'Все найденные версии совместимы с IGI Tools (' +
      IntToStr(MinSupportedYear) + '–' + IntToStr(MaxSupportedYear) + ').' + #13#10 +
      'Установка будет продолжена.';
    VersionSummaryLabel.Caption := Summary;
    ConfirmCheckBox.Visible := False;
    WizardForm.NextButton.Enabled := True;
  end
  else if Compatible = 0 then
  begin
    Summary :=
      'НИ ОДНА из установленных версий не поддерживается IGI Tools (' +
      IntToStr(MinSupportedYear) + '–' + IntToStr(MaxSupportedYear) + ').' + #13#10 +
      'Установка будет отменена.';
    VersionSummaryLabel.Caption := Summary;
    ConfirmCheckBox.Visible := False;
    WizardForm.NextButton.Enabled := False;
  end
  else
  begin
    Summary :=
      'ВНИМАНИЕ: Обнаружены неподдерживаемые версии.' + #13#10 +
      'Плагин будет доступен только на версиях ' +
      IntToStr(MinSupportedYear) + '–' + IntToStr(MaxSupportedYear) + '.' + #13#10 +
      'На остальных версиях работа не гарантируется.';
    VersionSummaryLabel.Caption := Summary;
    ConfirmCheckBox.Visible := True;
    ConfirmCheckBox.Checked := False;
    WizardForm.NextButton.Enabled := False;
  end;
end;

{-- Event handlers --------------------------------------------------------}

procedure ConfirmCheckBoxClick(Sender: TObject);
begin
  WizardForm.NextButton.Enabled := ConfirmCheckBox.Checked;
end;

{-- Setup lifecycle -------------------------------------------------------}

function GetBundlePath(Param: string): string;
begin
  Result := ExpandConstant('{commonpf64}') + '\Autodesk\ApplicationPlugins\{#MyBundleName}';
end;

function GetTemplatePath: string;
begin
  Result := ExpandConstant('{app}\Contents\Resources\template.dwg');
end;

function ExistingTemplateExists: Boolean;
begin
  Result := FileExists(GetTemplatePath());
end;

function ShouldInstallTemplate: Boolean;
begin
  { Первая установка — всегда; при наличии файла — только если выбрана задача. }
  if not ExistingTemplateExists then
    Result := True
  else
    Result := WizardIsTaskSelected('updatetemplate');
end;

function InitializeSetup(): Boolean;
var
  Compatible: Integer;
  Msg: string;
  I: Integer;
begin
  Result := True;
  Compatible := 0;

  if not CollectVersions then
  begin
    Msg :=
      'Не найдены установленные версии AutoCAD или Civil 3D.' + #13#10 +
      '' + #13#10 +
      'Плагин IGI Tools требует AutoCAD / Civil 3D ' +
      IntToStr(MinSupportedYear) + '–' + IntToStr(MaxSupportedYear) + '.' + #13#10 + #13#10 +
      'Установка будет отменена.';
    MsgBox(Msg, mbError, MB_OK);
    Result := False;
    Exit;
  end;

  Compatible := GetCompatibleCount;

  { Ни одна версия не подходит — тоже блокируем установку сразу }
  if Compatible = 0 then
  begin
    Msg :=
      'Установленные версии AutoCAD / Civil 3D не удовлетворяют требованиям.' + #13#10 +
      '' + #13#10 +
      'Требуется: ' + IntToStr(MinSupportedYear) + '–' + IntToStr(MaxSupportedYear) + #13#10 +
      'Найдены:' + #13#10;
    for I := 0 to VersionCount - 1 do
      Msg := Msg + '  [-] ' + VersionNames[I] + #13#10;
    Msg := Msg + #13#10 + 'Установка будет отменена.';
    MsgBox(Msg, mbError, MB_OK);
    Result := False;
    Exit;
  end;

  { Иначе (все совместимы или смешанный сценарий) — открываем мастер }
  Result := True;
end;

procedure InitializeWizard;
begin
  VersionCheckPage := CreateCustomPage(
    wpWelcome,
    'Проверка совместимости',
    'Обнаруженные версии AutoCAD / Civil 3D'
  );

  VersionSummaryLabel := TNewStaticText.Create(VersionCheckPage);
  VersionSummaryLabel.Parent := VersionCheckPage.Surface;
  VersionSummaryLabel.Left := 0;
  VersionSummaryLabel.Top := 8;
  VersionSummaryLabel.Width := VersionCheckPage.SurfaceWidth;
  VersionSummaryLabel.Height := 48;
  VersionSummaryLabel.WordWrap := True;

  VersionMemo := TMemo.Create(VersionCheckPage);
  VersionMemo.Parent := VersionCheckPage.Surface;
  VersionMemo.Left := 0;
  VersionMemo.Top := 64;
  VersionMemo.Width := VersionCheckPage.SurfaceWidth;
  VersionMemo.Height := VersionCheckPage.SurfaceHeight - 148;
  VersionMemo.ReadOnly := True;
  VersionMemo.ScrollBars := ssVertical;
  VersionMemo.WordWrap := False;
  VersionMemo.Font.Name := 'Consolas';
  VersionMemo.Font.Size := 9;
  VersionMemo.Color := clWhite;
  VersionMemo.TabOrder := 1;

  ConfirmCheckBox := TCheckBox.Create(VersionCheckPage);
  ConfirmCheckBox.Parent := VersionCheckPage.Surface;
  ConfirmCheckBox.Left := 0;
  ConfirmCheckBox.Top := VersionCheckPage.SurfaceHeight - 72;
  ConfirmCheckBox.Width := VersionCheckPage.SurfaceWidth;
  ConfirmCheckBox.Height := 32;
  ConfirmCheckBox.Caption :=
    'Продолжить установку (плагин будет работать только на поддерживаемых версиях)';
  ConfirmCheckBox.OnClick := @ConfirmCheckBoxClick;
  ConfirmCheckBox.Visible := False;
  ConfirmCheckBox.TabOrder := 2;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  { Страница проверки показывается всегда (если мастер открыт). }
  if PageID = VersionCheckPage.ID then
    Result := False
  else
    Result := False;  { стандартное поведение для остальных страниц }
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = VersionCheckPage.ID then
    PopulateVersionCheckPage;
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
