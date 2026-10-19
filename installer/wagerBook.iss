; Installer for Wager Book. Built with Inno Setup 6:
;
;     ISCC.exe installer\wagerBook.iss
;
; It expects dist\WagerBook\ to exist - run tools\buildExe.py first. The
; version and names are passed in by tools\buildInstaller.py so that they can
; never disagree with appConfig; the defaults below are only what a bare ISCC
; run would use.
;
; Per-user by design. The app keeps a person's own wagers in their own APPDATA;
; it needs nothing machine-wide, and asking for administrator rights to
; install a betting log is how a small tool becomes a thing IT has to approve.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef AppName
  #define AppName "Wager Book"
#endif
#ifndef ExeName
  #define ExeName "WagerBook.exe"
#endif
#ifndef BundleName
  #define BundleName "WagerBook"
#endif

#define Publisher "Charette AI Group, LLC"
#define AppUrl "https://github.com/Charette-AI-Group/wagerBook"
#define BundleDir "..\dist\" + BundleName

[Setup]
; Fixed for the life of the application: this is what lets an upgrade replace
; an install rather than sit beside it, and what the uninstaller is found by.
AppId={{6B9821D5-7AED-4B06-ABEF-8463C79139A9}
AppName={#AppName}
AppVersion={#AppVersion}
VersionInfoVersion={#AppVersion}
AppPublisher={#Publisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}
AppUpdatesURL={#AppUrl}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
SetupIconFile=..\src\wagerBook\resources\wagerBook.ico
UninstallDisplayIcon={app}\{#ExeName}
UninstallDisplayName={#AppName}
OutputDir=..\dist
OutputBaseFilename=wagerBookSetup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Per-user, so there is no UAC prompt and no Program Files. The application
; writes only to APPDATA, so nothing here needs more than the user has.
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Shown on the first page, so the licence is read before anything is written.
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; The bundle only. Deliberately not the book under APPDATA: an uninstall that
; silently discards somebody's record of every wager is a disaster, and a
; reinstall is the commonest reason to uninstall.
Type: filesandordirs; Name: "{app}\_internal"

[Code]
{ A running copy holds its own files open, so replacing them mid-upgrade
  fails with a message about a file in use that says nothing about why. Ask
  first instead, in words that name the application. The main window's title
  is exactly the app's name (appConfig.windowTitle).

  SuppressibleMsgBox, not MsgBox: a plain MsgBox still appears under
  /SUPPRESSMSGBOXES and would hang a silent install. Silently, the answer is
  No - abort cleanly rather than fail halfway on a file in use. }
function InitializeSetup(): Boolean;
var
  WindowHandle: HWND;
begin
  Result := True;
  WindowHandle := FindWindowByWindowName('{#AppName}');
  if WindowHandle <> 0 then
    Result := SuppressibleMsgBox(
      '{#AppName} appears to be running.' + #13#10#13#10 +
      'Close it before continuing, or setup cannot replace its files.' + #13#10#13#10 +
      'Continue anyway?',
      mbConfirmation, MB_YESNO, IDNO) = IDYES;
end;
