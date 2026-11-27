; PDFactory - Windows installer (Inno Setup 6). Built by .github/workflows/setup.yml:
;   iscc packaging\setup.iss /DMyVersion=0.2.1
; build\PDFactory holds the app with its own Python (python\PDFactory.exe = pythonw.exe with our icon).
#ifndef MyVersion
  #define MyVersion "0.0.0"
#endif

[Setup]
AppId={{C7CC6640-99AE-405F-91C8-31810DFAE0E4}
AppName=PDFactory
AppVersion={#MyVersion}
AppVerName=PDFactory {#MyVersion}
AppPublisher=Mirko Rudić
AppComments=Read and edit PDF files locally
DefaultDirName={localappdata}\Programs\PDFactory
DefaultGroupName=PDFactory
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
SetupIconFile=..\assets\pdfactory.ico
UninstallDisplayIcon={app}\python\PDFactory.exe
UninstallDisplayName=PDFactory
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=PDFactory-Setup-{#MyVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "autostart"; Description: "Start with Windows (opens PDF files instantly)"; GroupDescription: "Options:"
Name: "defaultapp"; Description: "Make PDFactory the default app for PDF files"; GroupDescription: "Options:"

[Files]
Source: "..\build\PDFactory\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Dirs]
Name: "{app}\data"

[Icons]
Name: "{autoprograms}\PDFactory"; Filename: "{app}\python\PDFactory.exe"; Parameters: """{app}\PDFactory.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\pdfactory.ico"
Name: "{autodesktop}\PDFactory"; Filename: "{app}\python\PDFactory.exe"; Parameters: """{app}\PDFactory.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\pdfactory.ico"; Tasks: desktopicon
Name: "{userstartup}\PDFactory"; Filename: "{app}\python\PDFactory.exe"; Parameters: """{app}\PDFactory.pyw"" --tiho"; WorkingDir: "{app}"; IconFilename: "{app}\assets\pdfactory.ico"; Tasks: autostart

[Run]
; the default app is chosen in Windows Settings; the app asks for it at its first start, with an explanation
Filename: "{app}\python\PDFactory.exe"; Parameters: """{app}\PDFactory.pyw"" --want-default"; WorkingDir: "{app}"; Tasks: defaultapp; Flags: runhidden waituntilterminated; Check: not WizardSilent
Filename: "{app}\python\PDFactory.exe"; Parameters: """{app}\PDFactory.pyw"""; WorkingDir: "{app}"; Description: "Open PDFactory"; Flags: postinstall nowait skipifsilent
; update from inside the app (silent, /RELAUNCH=window|tiho|none): start the new version again;
; an open window reloads by itself (--updated), after a background update only the tray icon comes back (--tiho)
Filename: "{app}\python\PDFactory.exe"; Parameters: """{app}\PDFactory.pyw"" --updated {code:RelaunchArgs}"; WorkingDir: "{app}"; Flags: nowait; Check: WizardSilent and Relaunch

[UninstallRun]
Filename: "{app}\python\PDFactory.exe"; Parameters: """{app}\PDFactory.pyw"" --uninstall"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "Unregister"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\app\__pycache__"

[Code]
// /WAITPID=<pid>: the app that started this update. Started at once, Setup found the app still running,
// could not close it (no window) and aborted (measured 26.11.2026, Windows 10); a hidden PowerShell that
// waited instead never started Setup on the workshop computer (27.11.2026). So Setup itself waits.
function OpenProcess(Access: Cardinal; Inherit: Boolean; Pid: Cardinal): THandle;
  external 'OpenProcess@kernel32.dll stdcall';
function WaitForSingleObject(Handle: THandle; Ms: Cardinal): Cardinal;
  external 'WaitForSingleObject@kernel32.dll stdcall';
function CloseHandle(Handle: THandle): Boolean;
  external 'CloseHandle@kernel32.dll stdcall';

function InitializeSetup: Boolean;
var
  Pid: Integer;
  H: THandle;
begin
  Result := True;
  Pid := StrToIntDef(ExpandConstant('{param:WAITPID|0}'), 0);
  if Pid > 0 then
  begin
    H := OpenProcess($00100000, False, Pid);   // SYNCHRONIZE
    if H <> 0 then
    begin
      Log(Format('waiting for pid %d', [Pid]));
      WaitForSingleObject(H, 60000);
      CloseHandle(H);
    end;
    Sleep(500);
  end;
end;

function Relaunch: Boolean;
begin
  Result := ExpandConstant('{param:RELAUNCH|window}') <> 'none';
end;

function RelaunchArgs(Param: String): String;
begin
  if ExpandConstant('{param:RELAUNCH|window}') = 'tiho' then Result := '--tiho' else Result := '';
end;
