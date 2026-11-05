#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif
[Setup]
AppId={{4805AB72-7459-4E65-96D9-CB907342A82F}
AppName=Codex Switch
AppVersion={#AppVersion}
AppPublisher=Found-L
AppPublisherURL=https://github.com/Found-L/codex-switch
AppSupportURL=https://github.com/Found-L/codex-switch/issues
DefaultDirName={localappdata}\Programs\CodexSwitch
DefaultGroupName=Codex Switch
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\release
OutputBaseFilename=CodexSwitch-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\codex-switch.ico
ChangesEnvironment=yes
UninstallDisplayIcon={app}\CodexSwitch.exe
LicenseFile=..\LICENSE
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: checkedonce
Name: "addtopath"; Description: "Add codex-switch to your user PATH"; Flags: checkedonce

[Files]
Source: "..\dist\CodexSwitch\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Codex Switch"; Filename: "{app}\CodexSwitch.exe"; AppUserModelID: "FoundL.CodexSwitch"
Name: "{userdesktop}\Codex Switch"; Filename: "{app}\CodexSwitch.exe"; AppUserModelID: "FoundL.CodexSwitch"; Tasks: desktopicon

[Run]
Filename: "{app}\CodexSwitch.exe"; Description: "Open Codex Switch"; Flags: nowait postinstall skipifsilent

[Code]
procedure UpdateUserPath(AddEntry: Boolean);
var CurrentPath, Remaining, NewPath, Part, AppPath: String; Separator: Integer; Found, First: Boolean;
begin
  AppPath := ExpandConstant('{app}');
  RegQueryStringValue(HKCU, 'Environment', 'Path', CurrentPath);
  Remaining := CurrentPath;
  NewPath := '';
  Found := False;
  First := True;
  repeat
    Separator := Pos(';', Remaining);
    if Separator > 0 then begin
      Part := Copy(Remaining, 1, Separator - 1);
      Delete(Remaining, 1, Separator);
    end else Part := Remaining;
    if CompareText(RemoveBackslash(Part), RemoveBackslash(AppPath)) <> 0 then begin
      if not First then NewPath := NewPath + ';';
      NewPath := NewPath + Part;
      First := False;
    end else Found := True;
  until Separator = 0;
  if AddEntry then begin
    if Found then Exit;
    NewPath := CurrentPath;
    if NewPath <> '' then NewPath := NewPath + ';';
    NewPath := NewPath + AppPath;
  end else if not Found then Exit;
  RegWriteExpandStringValue(HKCU, 'Environment', 'Path', NewPath);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    if WizardIsTaskSelected('addtopath') then UpdateUserPath(True);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var ResultCode: Integer; Launched: Boolean;
begin
  if CurUninstallStep = usUninstall then begin
    Launched := Exec(ExpandConstant('{app}\codex-switch.exe'), 'uninstall-cleanup', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    if (not Launched) or (ResultCode <> 0) then
      RaiseException('Cannot safely detach the API provider. Repair the affected Codex configuration and retry uninstalling.');
  end;
  if CurUninstallStep = usPostUninstall then UpdateUserPath(False);
end;
