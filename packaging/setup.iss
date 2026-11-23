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
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile=..\assets\pdfabrika.ico
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
Name: "{autoprograms}\PDFactory"; Filename: "{app}\python\PDFactory.exe"; Parameters: """{app}\PDFactory.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\pdfabrika.ico"
Name: "{autodesktop}\PDFactory"; Filename: "{app}\python\PDFactory.exe"; Parameters: """{app}\PDFactory.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\pdfabrika.ico"; Tasks: desktopicon
Name: "{userstartup}\PDFactory"; Filename: "{app}\python\PDFactory.exe"; Parameters: """{app}\PDFactory.pyw"" --tiho"; WorkingDir: "{app}"; IconFilename: "{app}\assets\pdfabrika.ico"; Tasks: autostart

[Run]
Filename: "{app}\python\PDFactory.exe"; Parameters: """{app}\PDFactory.pyw"" --default"; WorkingDir: "{app}"; Tasks: defaultapp; Flags: nowait; Check: not WizardSilent
Filename: "{app}\python\PDFactory.exe"; Parameters: """{app}\PDFactory.pyw"""; WorkingDir: "{app}"; Description: "Open PDFactory"; Flags: postinstall nowait skipifsilent
; update from inside the app (silent): start the new version again
Filename: "{app}\python\PDFactory.exe"; Parameters: """{app}\PDFactory.pyw"""; WorkingDir: "{app}"; Flags: nowait; Check: WizardSilent

[UninstallRun]
Filename: "{app}\python\PDFactory.exe"; Parameters: """{app}\PDFactory.pyw"" --uninstall"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "Unregister"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\app\__pycache__"
