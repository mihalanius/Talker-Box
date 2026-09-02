[Setup]
AppName=Talker Box
AppVersion=1.0.0
AppPublisher=mihalanius
DefaultDirName={autopf}\Talker Box
DefaultGroupName=Talker Box
OutputBaseFilename=TalkerBoxSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\talkerbox.ico
UninstallDisplayIcon={app}\TalkerBox.exe

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительно:"
Name: "autostart"; Description: "Автозапуск при загрузке Windows"; GroupDescription: "Дополнительно:"; Flags: checkedonce

[Files]
Source: "dist\TalkerBox\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\Talker Box"; Filename: "{app}\TalkerBox.exe"
Name: "{autostart}\Talker Box"; Filename: "{app}\TalkerBox.exe"; Parameters: "--minimized"; Tasks: autostart
Name: "{userdesktop}\Talker Box"; Filename: "{app}\TalkerBox.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "TalkerBox"; ValueData: """{app}\TalkerBox.exe"" --minimized"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\TalkerBox.exe"; Description: "Запустить Talker Box"; Flags: nowait postinstall skipifsilent
