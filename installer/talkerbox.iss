[Setup]
AppName=Talker Box
AppVersion=2.0.0
AppPublisher=mihalanius
DefaultDirName={localappdata}\Programs\Talker Box
DefaultGroupName=Talker Box
OutputBaseFilename=TalkerBoxSetup-v2.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
SetupIconFile=assets\talkerbox.ico
UninstallDisplayIcon={app}\TalkerBox.exe

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительно:"

[Files]
Source: "..\dist\TalkerBox\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\Talker Box"; Filename: "{app}\TalkerBox.exe"
Name: "{userdesktop}\Talker Box"; Filename: "{app}\TalkerBox.exe"; IconFilename: "{app}\TalkerBox.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "TalkerBox"; ValueData: """{app}\TalkerBox.exe"" --minimized"; Flags: uninsdeletevalue
