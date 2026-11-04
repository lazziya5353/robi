"""Robi'nin .py dosyalarındaki import'ları tarayıp _bagimliliklar.py'yi üretir (exe derlemesinden önce çalışır)."""
import ast
import importlib.util
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
OWN = {p.stem for p in ROOT.glob("*.py")}
EXTRA = ["webview.platforms.winforms", "webview.platforms.edgechromium", "clr_loader", "pythonnet", "pystray._win32",
         "PIL.ImageGrab", "PIL.ImageDraw", "docx.oxml.ns", "docx.shared", "lxml.etree", "encodings.idna",
         "ctypes.wintypes", "concurrent.futures", "html.parser", "winreg"]


def main():
    mods = set(EXTRA)
    for p in ROOT.glob("*.py"):
        if p.stem == "_bagimliliklar":
            continue
        src = p.read_text(encoding="utf-8")
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Import):
                mods.update(a.name for a in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                mods.add(n.module)
        mods.update(re.findall(r'__import__\("([\w.]+)"', src))
    keep = []
    for m in sorted(mods):
        if m.split(".")[0] in OWN:
            continue
        try:
            if importlib.util.find_spec(m) is None:
                continue
        except Exception:
            continue
        keep.append(m)
    body = "\n".join(f"    import {m}  # noqa" for m in keep)
    (ROOT / "_bagimliliklar.py").write_text(
        '"""\nSadece Robi.exe derlemesi için: Robi\'nin kod dosyaları exe\'ye gömülmediği (güncellenebilsinler diye)\n'
        "için PyInstaller onların kullandığı kütüphaneleri göremez. Bu liste onları exe'ye dahil ettirir.\n"
        "Fonksiyon hiç çağrılmaz. Derlemeden önce araclar/bagimlilik_uret.py ile otomatik üretilir.\n\"\"\"\n\n\n"
        f"def _liste():\n{body}\n", encoding="utf-8")
    print(f"{len(keep)} modules written")


if __name__ == "__main__":
    main()
