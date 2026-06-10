[Setup]
AppName=SmartSocialMedia
AppVersion=3.0
DefaultDirName={autopf}\SmartSocialMedia
DefaultGroupName=SmartSocialMedia
OutputDir=C:\PROGRAMOWANIE\SmartSocialMedia\installer
OutputBaseFilename=Setup_SmartSocialMedia
SetupIconFile=C:\PROGRAMOWANIE\SmartSocialMedia\assets\icon.ico
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest

[Tasks]
Name: "desktopicon"; Description: "Utwórz skrót na pulpicie"; GroupDescription: "Dodatkowe skróty:"

[Files]
Source: "C:\PROGRAMOWANIE\SmartSocialMedia\dist\SmartSocialMedia\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "C:\PROGRAMOWANIE\SmartSocialMedia\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
; Empty dirs for data and logs
Source: "C:\PROGRAMOWANIE\SmartSocialMedia\dist\SmartSocialMedia\SmartSocialMedia.exe"; DestDir: "{app}"; DestName: ".empty_keep_dir"; Flags: skipifsourcedoesntexist

[Dirs]
Name: "{app}\data"
Name: "{app}\logs"
Name: "{app}\raporty"

[Icons]
Name: "{group}\SmartSocialMedia"; Filename: "{app}\SmartSocialMedia.exe"; IconFilename: "{app}\assets\icon.ico"
Name: "{commondesktop}\SmartSocialMedia"; Filename: "{app}\SmartSocialMedia.exe"; Tasks: desktopicon; IconFilename: "{app}\assets\icon.ico"

[Run]
Filename: "{app}\SmartSocialMedia.exe"; Description: "Uruchom SmartSocialMedia"; Flags: nowait postinstall skipifsilent
