; Robi Kurulum — Inno Setup betiği (GitHub Actions'ta otomatik derlenir)
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6B7E2C41-9A5D-4F3B-8E21-52A9C0D7F1B3}
AppName=Robi
AppVersion={#AppVersion}
AppVerName=Robi {#AppVersion}
AppPublisher=lazziya5353
AppPublisherURL=https://github.com/lazziya5353/robi
; Kullanıcının kendi klasörüne kurulur: yönetici izni gerekmez ve Robi kendini güncelleyebilir
DefaultDirName={localappdata}\Programs\Robi
PrivilegesRequired=lowest
DisableDirPage=yes
DisableProgramGroupPage=yes
DefaultGroupName=Robi
OutputDir=..\Output
OutputBaseFilename=RobiKurulum
SetupIconFile=..\robi.ico
UninstallDisplayIcon={app}\Robi.exe
UninstallDisplayName=Robi
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=no
CloseApplications=force
RestartApplications=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne Robi kısayolu koy"
Name: "autostart"; Description: "Windows açılınca Robi'yi otomatik başlat (telefondan iş vermek için önerilir)"

[Files]
; Program (Python ve kütüphaneler içinde)
Source: "..\dist\Robi\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Robi'nin kendi kodu (güncellemelerle yenilenir)
Source: "..\paket\*"; DestDir: "{app}"; Excludes: "config.json"; Flags: ignoreversion recursesubdirs createallsubdirs
; Ayarlar sadece ilk kurulumda konur, sonra kullanıcınınki korunur
Source: "..\paket\config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{autoprograms}\Robi"; Filename: "{app}\Robi.exe"; Comment: "Bilgisayar yardımcı robotu"
Name: "{autodesktop}\Robi"; Filename: "{app}\Robi.exe"; Tasks: desktopicon
Name: "{userstartup}\Robi"; Filename: "{app}\Robi.exe"; Tasks: autostart

[Run]
Filename: "{app}\Robi.exe"; Description: "Robi'yi şimdi başlat"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\yedek"

[Messages]
turkish.WelcomeLabel2=Robi bilgisayarına kurulacak.%n%nKurulumdan sonra ⚙️ Ayarlar'dan Claude API anahtarını girmen yeterli. İstersen Telegram'ı da bağlayıp telefondan iş verebilirsin.
