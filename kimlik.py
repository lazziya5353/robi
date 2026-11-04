"""
Robi'nin Windows'taki kimliği: ikon, görev çubuğu görünümü, masaüstü/Başlat menüsü kısayolu.
"""
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ICON = BASE / "robi.ico"
SHORTCUT_FLAG = BASE / "kisayol.ok"
APP_ID = "Robi.BilgisayarAsistani"
IS_WINDOWS = sys.platform.startswith("win")
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def make_icon_image(size: int = 256):
    """Mor robot ikonu (64'lük tasarım, istenen boyuta ölçeklenir)."""
    from PIL import Image, ImageDraw
    k = size / 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = lambda *v: tuple(round(x * k) for x in v)
    d.rounded_rectangle(s(6, 10, 58, 54), radius=round(14 * k), fill=(124, 92, 255))
    d.ellipse(s(18, 24, 28, 34), fill="white")
    d.ellipse(s(36, 24, 46, 34), fill="white")
    d.rounded_rectangle(s(22, 41, 42, 45), radius=max(1, round(2 * k)), fill="white")
    d.line(s(32, 10, 32, 3), fill=(124, 92, 255), width=max(1, round(3 * k)))
    d.ellipse(s(28, 0, 36, 7), fill=(0, 220, 180))
    return img


def ensure_icon():
    if not ICON.exists():
        make_icon_image(256).save(ICON, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return ICON


def set_app_id():
    """Görev çubuğunda Python olarak değil, ayrı bir 'Robi' uygulaması olarak görünsün."""
    if IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass


def apply_window_icon():
    """Bu programın açtığı pencerelere Robi ikonunu ver (başlık çubuğu + görev çubuğu)."""
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        from ctypes import wintypes
        u32 = ctypes.windll.user32
        LR_LOADFROMFILE, IMAGE_ICON, WM_SETICON = 0x10, 1, 0x80
        big = u32.LoadImageW(None, str(ensure_icon()), IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
        small = u32.LoadImageW(None, str(ICON), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        pid = os.getpid()

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cb(hwnd, _):
            owner = wintypes.DWORD()
            u32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid and u32.IsWindowVisible(hwnd):
                u32.SendMessageW(hwnd, WM_SETICON, 1, big)
                u32.SendMessageW(hwnd, WM_SETICON, 0, small)
            return True

        u32.EnumWindows(cb, 0)
    except Exception as e:
        print("Pencere ikonu ayarlanamadı:", e)


def _pythonw():
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return w if w.exists() else exe


def _make_lnk(folder_ps: str, name: str, only_if_exists: bool = False):
    target = f"[Environment]::GetFolderPath('{folder_ps}')"
    check = f"if (-not (Test-Path \"$d\\{name}.lnk\")) {{ exit }}; " if only_if_exists else ""
    ps = (
        f"$d={target}; {check}"
        f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut(\"$d\\{name}.lnk\"); "
        "$s.TargetPath=$env:ROBI_EXE; if ($env:ROBI_APP) { $s.Arguments='\"' + $env:ROBI_APP + '\"' }; "
        "$s.WorkingDirectory=$env:ROBI_DIR; $s.IconLocation=$env:ROBI_ICO; "
        "$s.Description='Bilgisayar yardımcı robotu'; $s.Save()"
    )
    frozen = getattr(sys, "frozen", False)  # Robi.exe ise doğrudan exe'yi çalıştır
    env = {**os.environ, "ROBI_EXE": str(sys.executable if frozen else _pythonw()),
           "ROBI_APP": "" if frozen else str(BASE / "baslatici.py"),
           "ROBI_DIR": str(BASE), "ROBI_ICO": str(ensure_icon())}
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, timeout=20, creationflags=_NO_WINDOW)


SHORTCUT_VERSION = "v3"  # kısayolun hedefi değişince artır


def create_shortcuts(name: str = "Robi"):
    """İlk açılışta masaüstü + Başlat menüsü kısayolu oluşturur. Kullanıcı silerse tekrar zorla oluşturmaz;
    kısayolun hedefi değiştiğinde sadece var olan kısayolları yeniler."""
    if not IS_WINDOWS:
        return
    current = SHORTCUT_FLAG.read_text().strip() if SHORTCUT_FLAG.exists() else ""
    if current == SHORTCUT_VERSION:
        return
    try:
        first_time = current == ""
        _make_lnk("Desktop", name, only_if_exists=not first_time)
        _make_lnk("Programs", name, only_if_exists=not first_time)
        _make_lnk("Startup", name, only_if_exists=True)  # açılışta başlama varsa onu da yenile
        SHORTCUT_FLAG.write_text(SHORTCUT_VERSION)
    except Exception as e:
        print("Kısayol oluşturulamadı:", e)


def add_to_startup(name: str = "Robi"):
    if IS_WINDOWS:
        _make_lnk("Startup", name)
