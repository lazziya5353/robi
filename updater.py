"""
Robi'nin kendini GitHub'dan güncellemesi.
- Ayarlar (config.json), anahtar (gizli.json) ve sohbetler klasörü ASLA ezilmez.
- Kurulu sürüm 'surum.txt' içinde (GitHub commit kodu) tutulur.
"""
import io
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
SECRET = BASE / "gizli.json"
VERSION = BASE / "surum.txt"
VARSAYILAN_REPO = "lazziya5353/robi"  # GitHub reposu: "kullanici/robi"
KORUNAN = {"config.json", "gizli.json", "surum.txt", "sohbetler", "__pycache__", ".git",
           "yedek", "yeni_guncelleme", "hata.log", "atla.txt", "kisayol.ok", "robi.ico"}
BACKUP = BASE / "yedek"
FRESH = BASE / "yeni_guncelleme"
SKIP = BASE / "atla.txt"


def _token():
    try:
        return json.loads(SECRET.read_text(encoding="utf-8")).get("github_token", "").strip()
    except Exception:
        return ""


def token_kaydet(token: str):
    SECRET.write_text(json.dumps({"github_token": token.strip()}), encoding="utf-8")


def _headers():
    h = {"Accept": "application/vnd.github+json", "User-Agent": "Robi-guncelleyici"}
    t = _token()
    if t:
        h["Authorization"] = "Bearer " + t
    return h


def kontrol(repo: str, dal: str = "main"):
    """Döner: {durum: 'kapali'|'token_yok'|'guncel'|'var'|'hata', ...}"""
    if not repo:
        return {"durum": "kapali"}
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}/commits/{dal}", headers=_headers(), timeout=10)
    except Exception as e:
        return {"durum": "hata", "mesaj": f"GitHub'a ulaşılamadı: {e}"}
    if r.status_code != 200 and not _token():
        return {"durum": "token_yok"}
    if r.status_code == 401:
        return {"durum": "hata", "mesaj": "Anahtar geçersiz ya da süresi dolmuş (401). Yanlış kopyalanmış olabilir, yeni anahtar gir."}
    if r.status_code == 409:
        return {"durum": "hata", "mesaj": "Repo boş görünüyor (409). GitHub'da dosyaları yükleyip Commit changes'a bastığından emin ol."}
    if r.status_code in (403, 404, 422):
        # Sorun repoda mı, izinde mi, dalda mı?
        try:
            rr = requests.get(f"https://api.github.com/repos/{repo}", headers=_headers(), timeout=10)
        except Exception:
            rr = None
        if rr is not None and rr.status_code == 200:
            default = rr.json().get("default_branch", dal)
            if default != dal:
                return kontrol(repo, default)
            return {"durum": "hata", "mesaj": f"Anahtarın kodu okuma izni yok ({r.status_code}). Token ayarında Permissions → Contents → Read-only ekle."}
        return {"durum": "hata", "mesaj": f"Anahtar '{repo}' reposunu göremiyor ({r.status_code}). Token ayarında Repository access kısmında robi seçili olmalı."}
    if r.status_code != 200:
        return {"durum": "hata", "mesaj": f"GitHub hatası ({r.status_code})"}
    d = r.json()
    sha = d["sha"]
    local = VERSION.read_text().strip() if VERSION.exists() else ""
    skipped = SKIP.read_text().strip() if SKIP.exists() else ""
    if sha == local or sha == skipped:  # bozuk çıkıp geri alınan sürümü tekrar önerme
        return {"durum": "guncel"}
    msg = d.get("commit", {}).get("message", "").split("\n")[0]
    return {"durum": "var", "sha": sha, "mesaj": msg}


def guncelle(repo: str, dal: str = "main"):
    info = kontrol(repo, dal)
    if info["durum"] != "var":
        return info
    r = requests.get(f"https://api.github.com/repos/{repo}/zipball/{info['sha']}", headers=_headers(), timeout=60)
    r.raise_for_status()
    _yedekle()
    old_req = (BASE / "requirements.txt").read_text(encoding="utf-8") if (BASE / "requirements.txt").exists() else ""

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        root = z.namelist()[0].split("/")[0] + "/"
        for name in z.namelist():
            rel = name[len(root):]
            if not rel or rel.split("/")[0] in KORUNAN:
                continue
            dest = BASE / rel
            if name.endswith("/"):
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(name) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)

    new_req = (BASE / "requirements.txt").read_text(encoding="utf-8") if (BASE / "requirements.txt").exists() else ""
    if new_req != old_req:  # yeni kütüphane geldiyse kur
        py = Path(sys.executable)
        if py.name.lower() == "pythonw.exe":
            py = py.with_name("python.exe")
        subprocess.run([str(py), "-m", "pip", "install", "-r", str(BASE / "requirements.txt")],
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    VERSION.write_text(info["sha"])
    FRESH.write_text(info["sha"])  # ilk açılış başarılı olursa silinir; çökerse başlatıcı geri alır
    return {"durum": "tamam", "mesaj": info["mesaj"]}


def _yedekle():
    """Güncellemeden önce çalışan sürümün kodunu yedek/ klasörüne al."""
    if BACKUP.exists():
        shutil.rmtree(BACKUP, ignore_errors=True)
    BACKUP.mkdir()
    for f in BASE.rglob("*"):
        rel = f.relative_to(BASE)
        if f.is_dir() or rel.parts[0] in KORUNAN:
            continue
        dest = BACKUP / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
    if VERSION.exists():
        shutil.copy2(VERSION, BACKUP / "surum.txt")


def yeniden_baslat():
    exe = Path(sys.executable)
    if exe.name.lower() == "python.exe" and exe.with_name("pythonw.exe").exists():
        exe = exe.with_name("pythonw.exe")
    starter = BASE / "baslatici.py"
    subprocess.Popen([str(exe), str(starter if starter.exists() else BASE / "app.py"), "--yeniden"], cwd=str(BASE))
