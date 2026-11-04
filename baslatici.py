"""
Robi başlatıcısı — kısayollar bunu çalıştırır.
Robi açılırken çökerse: hatayı hata.log'a yazar, son güncelleme yeni yapıldıysa
önceki çalışan sürüme geri döner ve kullanıcıya haber verir.
"""
import os
import shutil
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)  # Robi.exe olarak mı çalışıyor?
# exe'de kod dosyaları exe'nin yanında durur (güncellenebilsin diye exe'ye gömülmez)
BASE = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
LOG = BASE / "hata.log"
BACKUP = BASE / "yedek"
FRESH = BASE / "yeni_guncelleme"   # güncellemeden sonra ilk başarılı açılışta silinir
SKIP = BASE / "atla.txt"           # bozuk çıkan sürüm bir daha önerilmesin


def log(text: str):
    try:
        old = LOG.read_text(encoding="utf-8")[-50000:] if LOG.exists() else ""
        LOG.write_text(old + f"\n===== {datetime.now():%d.%m.%Y %H:%M:%S} =====\n{text}\n", encoding="utf-8")
    except Exception:
        pass


def msgbox(text: str, title: str = "Robi"):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x40 | 0x40000)  # bilgi ikonu, en üstte
    except Exception:
        print(text)


def rollback() -> bool:
    if not BACKUP.exists() or not any(BACKUP.iterdir()):
        return False
    broken = (BASE / "surum.txt").read_text().strip() if (BASE / "surum.txt").exists() else ""
    for src in BACKUP.rglob("*"):
        if src.is_file():
            dest = BASE / src.relative_to(BACKUP)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    if broken:
        SKIP.write_text(broken)
    return True


def relaunch():
    if FROZEN:
        subprocess.Popen([sys.executable, "--yeniden"], cwd=str(BASE))
        return
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    subprocess.Popen([str(w if w.exists() else exe), str(BASE / "baslatici.py"), "--yeniden"], cwd=str(BASE))


def main():
    os.chdir(BASE)
    sys.path.insert(0, str(BASE))
    try:
        if FROZEN:
            import _bagimliliklar  # noqa: F401  (exe'ye gerekli kütüphaneleri dahil ettirir)
        import importlib
        app = importlib.import_module("app")  # exe'nin yanındaki app.py (güncellenebilir)
        app.main()
    except SystemExit:
        raise
    except Exception:
        tb = traceback.format_exc()
        log(tb)
        if FRESH.exists() and rollback():
            FRESH.unlink(missing_ok=True)
            log("Önceki sürüme geri dönüldü.")
            msgbox("Son güncelleme Robi'yi açılmaz hale getirdi, bu yüzden önceki çalışan sürüme geri döndüm. 👍\n\n"
                   "Hata kaydı: robi klasöründeki hata.log\nBu dosyayı Claude'a gönderirsen düzeltir.")
            relaunch()
        else:
            last = "\n".join(tb.strip().splitlines()[-4:])
            msgbox(f"Robi açılırken bir hata oldu:\n\n{last}\n\nDetay: robi klasöründeki hata.log")


if __name__ == "__main__":
    main()
