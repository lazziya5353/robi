"""
Robi'nin elleri: bilgisayarda yapabildiği işler.

Her araç üç seviyeden birine ait:
  YESIL  -> direkt yapar
  SARI   -> önce kullanıcıdan onay ister
Kırmızı işler (şifre, kart, sistem ayarı, para) için araç hiç yok; robot bunları yapamaz.
"""
import os
import sys
import glob
import shutil
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path

import psutil

try:
    from send2trash import send2trash  # silinenler Geri Dönüşüm Kutusu'na gider
except ImportError:  # pragma: no cover
    send2trash = None

IS_WINDOWS = sys.platform.startswith("win")
HOME = Path.home()

# ----------------------------------------------------------------------------
# Yardımcılar
# ----------------------------------------------------------------------------

def _known_folder(name: str) -> Path:
    """'masaüstü', 'indirilenler' gibi Türkçe adları gerçek klasöre çevirir."""
    n = (name or "").strip().lower()
    aliases = {
        ("masaüstü", "masaustu", "desktop"): ["Desktop", "OneDrive/Desktop", "OneDrive/Masaüstü", "Masaüstü"],
        ("indirilenler", "downloads", "indirmeler"): ["Downloads", "İndirilenler"],
        ("belgeler", "documents", "belgelerim"): ["Documents", "OneDrive/Documents", "OneDrive/Belgeler", "Belgeler"],
        ("resimler", "pictures", "fotoğraflar", "fotograflar"): ["Pictures", "OneDrive/Pictures", "Resimler"],
        ("videolar", "videos"): ["Videos", "Videolar"],
        ("müzik", "muzik", "music"): ["Music", "Müzik"],
        ("ev", "home", "kullanıcı", "kullanici"): [""],
    }
    for keys, subs in aliases.items():
        if n in keys:
            for s in subs:
                p = HOME / s
                if p.exists():
                    return p
            return HOME / subs[0]
    if n == "temp" or n == "geçici" or n == "gecici":
        return Path(os.environ.get("TEMP", "/tmp"))
    return Path(os.path.expandvars(os.path.expanduser(name)))


def _fmt_size(b: float) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {unit}" if unit != "B" else f"{int(b)} B"
        b /= 1024
    return f"{b:.1f} PB"


def _fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%d.%m.%Y")


# Bu klasörlere asla dokunma
_PROTECTED = []
if IS_WINDOWS:
    for env in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        v = os.environ.get(env)
        if v:
            _PROTECTED.append(Path(v).resolve())


def _is_protected(p: Path) -> bool:
    try:
        rp = p.resolve()
    except Exception:
        return True
    if rp == rp.anchor or str(rp) == rp.anchor or rp == HOME.resolve():
        return True  # sürücü kökü veya kullanıcı klasörünün kendisi
    for prot in _PROTECTED:
        if rp == prot or prot in rp.parents:
            return True
    return False


# ----------------------------------------------------------------------------
# YEŞİL araçlar (direkt çalışır)
# ----------------------------------------------------------------------------

def sistem_bilgisi():
    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(part.mountpoint)
        except Exception:
            continue
        disks.append({
            "sürücü": part.mountpoint,
            "toplam": _fmt_size(u.total),
            "boş": _fmt_size(u.free),
            "doluluk": f"%{u.percent:.0f}",
        })
    vm = psutil.virtual_memory()
    return {
        "işlemci_kullanımı": f"%{psutil.cpu_percent(interval=0.5):.0f}",
        "çekirdek": psutil.cpu_count(),
        "ram_toplam": _fmt_size(vm.total),
        "ram_kullanılan": f"%{vm.percent:.0f}",
        "diskler": disks,
        "açık_kalma_süresi_saat": round((datetime.now().timestamp() - psutil.boot_time()) / 3600, 1),
    }


def klasor_listele(klasor: str = "masaüstü", adet: int = 50):
    p = _known_folder(klasor)
    if not p.exists():
        return {"hata": f"Klasör bulunamadı: {p}"}
    items = []
    for e in p.iterdir():
        if e.name.startswith(".") or e.name.lower() in ("desktop.ini", "thumbs.db"):
            continue  # gizli sistem dosyalarını gösterme
        try:
            st = e.stat()
        except Exception:
            continue
        items.append({
            "ad": e.name,
            "tür": "klasör" if e.is_dir() else (e.suffix.lower() or "dosya"),
            "boyut": "" if e.is_dir() else _fmt_size(st.st_size),
            "son_değişiklik": _fmt_time(st.st_mtime),
            "son_erişim": _fmt_time(st.st_atime),
            "yol": str(e),
        })
    items.sort(key=lambda x: x["ad"].lower())
    return {"klasör": str(p), "toplam": len(items), "öğeler": items[: int(adet)]}


def dosya_ara(desen: str, klasor: str = "ev", adet: int = 30):
    root = _known_folder(klasor)
    if not root.exists():
        return {"hata": f"Klasör bulunamadı: {root}"}
    pat = desen if any(c in desen for c in "*?") else f"*{desen}*"
    found = []
    for path in root.rglob(pat):
        try:
            st = path.stat()
        except Exception:
            continue
        found.append({"yol": str(path), "boyut": _fmt_size(st.st_size), "tarih": _fmt_time(st.st_mtime)})
        if len(found) >= int(adet):
            break
    return {"aranan": pat, "klasör": str(root), "bulunan": found}


def buyuk_dosyalar(klasor: str = "ev", adet: int = 15):
    root = _known_folder(klasor)
    if not root.exists():
        return {"hata": f"Klasör bulunamadı: {root}"}
    sizes = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("AppData", "node_modules")]
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                sizes.append((os.path.getsize(fp), fp))
            except Exception:
                pass
    sizes.sort(reverse=True)
    return {"klasör": str(root), "en_büyükler": [{"yol": p, "boyut": _fmt_size(s)} for s, p in sizes[: int(adet)]]}


def _registry_apps():
    import winreg
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    apps = {}
    for hive, key in roots:
        try:
            k = winreg.OpenKey(hive, key)
        except OSError:
            continue
        for i in range(winreg.QueryInfoKey(k)[0]):
            try:
                sub = winreg.OpenKey(k, winreg.EnumKey(k, i))
            except OSError:
                continue

            def val(n):
                try:
                    return winreg.QueryValueEx(sub, n)[0]
                except OSError:
                    return None

            name = val("DisplayName")
            if not name or val("SystemComponent") == 1 or val("ParentKeyName"):
                continue
            install = val("InstallDate")
            apps[name] = {
                "ad": name,
                "yayıncı": val("Publisher") or "",
                "kurulum_tarihi": f"{install[6:8]}.{install[4:6]}.{install[:4]}" if install and len(str(install)) == 8 else "",
                "boyut": _fmt_size(val("EstimatedSize") * 1024) if val("EstimatedSize") else "",
                "_kaldir": val("QuietUninstallString") or val("UninstallString"),
            }
    return sorted(apps.values(), key=lambda a: a["ad"].lower())


def uygulamalari_listele():
    if not IS_WINDOWS:
        return {"hata": "Bu araç sadece Windows'ta çalışır."}
    apps = _registry_apps()
    return {
        "toplam": len(apps),
        "uygulamalar": [{k: v for k, v in a.items() if not k.startswith("_")} for a in apps],
        "not": "Gereksiz olabilecekleri seçerken: deneme sürümleri, üretici reklam yazılımları, uzun zamandır güncellenmemiş araçlar, aynı işi yapan birden fazla program.",
    }


_APP_ALIASES = {
    "chrome": "chrome", "google chrome": "chrome", "krom": "chrome",
    "edge": "msedge", "not defteri": "notepad", "notepad": "notepad",
    "hesap makinesi": "calc", "calc": "calc", "paint": "mspaint",
    "dosya gezgini": "explorer", "gezgin": "explorer", "explorer": "explorer",
    "görev yöneticisi": "taskmgr", "gorev yoneticisi": "taskmgr",
    "spotify": "spotify:", "discord": "discord:", "steam": "steam:",
    "ayarlar": "ms-settings:", "word": "winword", "excel": "excel",
}


_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _shortcut_dirs():
    appdata = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
    progdata = Path(os.environ.get("ProgramData", "C:/ProgramData"))
    return [
        appdata / "Microsoft/Internet Explorer/Quick Launch/User Pinned/TaskBar",  # görev çubuğu
        appdata / "Microsoft/Windows/Start Menu/Programs",                          # başlat menüsü (kullanıcı)
        progdata / "Microsoft/Windows/Start Menu/Programs",                         # başlat menüsü (herkes)
        HOME / "Desktop", HOME / "OneDrive/Desktop", HOME / "OneDrive/Masaüstü",
    ]


def _norm(s: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return s.translate(tr).lower().strip()


def _find_shortcut(ad: str):
    """Görev çubuğu, başlat menüsü ve masaüstündeki kısayollarda uygulamayı arar."""
    want = _norm(ad)
    exact, partial = None, None
    for d in _shortcut_dirs():
        if not d.exists():
            continue
        for lnk in d.rglob("*.lnk"):
            name = _norm(lnk.stem)
            if name == want:
                return lnk
            if partial is None and want in name and "uninstall" not in name and "kaldir" not in name:
                partial = lnk
    return exact or partial


def _read_shortcut(lnk: Path):
    """Kısayolun hedefini ve parametrelerini okur."""
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:ROBI_LNK);"
          "Write-Output $s.TargetPath; Write-Output $s.Arguments")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                             timeout=10, creationflags=_NO_WINDOW, env={**os.environ, "ROBI_LNK": str(lnk)})
        lines = out.stdout.splitlines() + ["", ""]
        return lines[0].strip(), lines[1].strip()
    except Exception:
        return "", ""


def uygulama_ac(ad: str):
    if IS_WINDOWS:
        lnk = _find_shortcut(ad)
        if lnk:
            os.startfile(str(lnk))
            return {"tamam": f"'{lnk.stem}' kısayolu çalıştırıldı.", "kisayol": str(lnk)}
    target = _APP_ALIASES.get(ad.strip().lower())
    if not target:
        return {"hata": f"'{ad}' adında bir uygulama ya da kısayol bulamadım. AÇILMADI."}
    try:
        if IS_WINDOWS:
            subprocess.Popen(["cmd", "/c", "start", "", target], creationflags=_NO_WINDOW)
        else:
            subprocess.Popen([target])
        return {"tamam": f"'{ad}' açılıyor."}
    except Exception as e:
        return {"hata": f"Açılamadı: {e}"}


def _open_in_web_app(app_name: str, url: str):
    """Chrome/Edge'e yüklenmiş web uygulamasında (ör. YouTube uygulaması) belirli bir adresi açar.
    Uygulama yoksa None döner."""
    if not IS_WINDOWS:
        return None
    lnk = _find_shortcut(app_name)
    if not lnk:
        return None
    target, args = _read_shortcut(lnk)
    import re
    m = re.search(r"--app-id=(\S+)", args)
    if not target or not m:
        return None
    cmd = [target]
    p = re.search(r'--profile-directory=("[^"]+"|\S+)', args)
    if p:
        cmd.append("--profile-directory=" + p.group(1).strip('"'))
    cmd += ["--app-id=" + m.group(1), "--app-launch-url-for-shortcuts-menu-item=" + url]
    subprocess.Popen(cmd, creationflags=_NO_WINDOW)
    return str(lnk)


def web_ac(adres: str):
    if not adres.startswith(("http://", "https://")):
        adres = "https://" + adres
    webbrowser.open(adres)
    return {"tamam": f"{adres} varsayılan TARAYICIDA açıldı (uygulamada değil)."}


# --------------------------- Ses, medya, güç ---------------------------

def ses_medya(islem: str, deger: int = 10):
    import hizli
    if islem in ("ac", "kis", "sessiz", "yuzde"):
        return {"tamam": hizli.ses(islem, int(deger or 10))}
    if islem in ("oynat", "sonraki", "onceki"):
        return {"tamam": hizli.medya(islem)}
    if islem == "kilitle":
        return {"tamam": hizli.kilitle()}
    return {"hata": f"Bilinmeyen işlem: {islem}"}


def zamanli_kapat(dakika: int = 0, iptal: bool = False):
    import hizli
    if iptal:
        return {"tamam": hizli.kapatma_iptal()}
    return {"tamam": hizli.zamanli_kapat(int(dakika))}


# --------------------------- Not / dosya kaydetme ---------------------------

def not_kaydet(baslik: str, icerik: str, klasor: str = "masaüstü", ac: bool = True):
    """Yeni bir .txt dosyası oluşturur. Var olan dosyanın üstüne ASLA yazmaz (adına sayı ekler)."""
    import re
    folder = _known_folder(klasor)
    if _is_protected(folder / "x"):
        return {"hata": "Bu klasöre yazamam."}
    folder.mkdir(parents=True, exist_ok=True)
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', "", baslik).strip()[:60] or "Robi notu"
    path = folder / f"{name}.txt"
    n = 2
    while path.exists():
        path = folder / f"{name} ({n}).txt"
        n += 1
    path.write_text(icerik.replace("\r\n", "\n").replace("\n", "\r\n"), encoding="utf-8-sig")
    if ac and IS_WINDOWS:
        subprocess.Popen(["notepad.exe", str(path)])
    return {"tamam": "Not kaydedildi" + (" ve Not Defteri'nde açıldı." if ac else "."), "dosya": str(path)}


# --------------------------- İnternet araştırması ---------------------------

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
       "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"}


def _strip_tags(s):
    import re, html as _h
    return _h.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def _search_ddg(q):
    import re, requests
    from urllib.parse import unquote, urlparse, parse_qs
    r = requests.post("https://html.duckduckgo.com/html/", data={"q": q, "kl": "tr-tr"}, headers=_UA, timeout=15)
    out = []
    blocks = re.split(r'<div class="result results_links', r.text)[1:]
    for b in blocks:
        a = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
        if not a:
            continue
        href = a.group(1)
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
        if href.startswith("//"):
            href = "https:" + href
        if "duckduckgo.com/y.js" in href:  # reklam
            continue
        sn = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', b, re.S)
        out.append({"başlık": _strip_tags(a.group(2)), "adres": href, "özet": _strip_tags(sn.group(1)) if sn else ""})
    return out


def _search_bing(q):
    import re, requests
    from urllib.parse import quote_plus
    r = requests.get("https://www.bing.com/search?setlang=tr&cc=TR&q=" + quote_plus(q), headers=_UA, timeout=15)
    out = []
    for b in re.findall(r'<li class="b_algo"(.*?)</li>', r.text, re.S):
        a = re.search(r'<h2[^>]*>\s*<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', b, re.S)
        if not a:
            continue
        sn = re.search(r"<p[^>]*>(.*?)</p>", b, re.S)
        out.append({"başlık": _strip_tags(a.group(2)), "adres": a.group(1), "özet": _strip_tags(sn.group(1)) if sn else ""})
    return out


def web_ara(arama: str, adet: int = 6):
    results, errors = [], []
    for fn in (_search_ddg, _search_bing):
        try:
            results = fn(arama)
        except Exception as e:
            errors.append(str(e))
            results = []
        if results:
            break
    if not results:
        return {"hata": "Arama sonucu alınamadı.", "detay": errors}
    return {"arama": arama, "sonuçlar": results[: int(adet)],
            "not": "Şimdi en uygun 1-2 sonucu sayfa_oku ile oku. Adres uydurma, sadece bu adresleri kullan."}


class _TextExtractor(__import__("html.parser", fromlist=["HTMLParser"]).HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe", "button", "aside"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "table", "ul", "ol"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip, self.title, self._in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "tr":
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append(" | ")
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.parts.append(data)

    def text(self):
        import re
        t = "".join(self.parts)
        t = re.sub(r"[ \t\r\f\v]+", " ", t)
        t = re.sub(r" *\n[ \n|]*\n", "\n", t)
        lines = [l.strip() for l in t.split("\n")]
        return "\n".join(l for l in lines if len(l) > 1)


def sayfa_oku(adres: str, odak: str = "", baslangic: int = 0):
    import requests
    if not adres.startswith(("http://", "https://")):
        adres = "https://" + adres
    try:
        r = requests.get(adres, headers=_UA, timeout=20)
    except Exception as e:
        return {"hata": f"Sayfaya girilemedi: {e}"}
    if r.status_code >= 400:
        return {"hata": f"Sayfa açılmadı (HTTP {r.status_code}). Başka bir sonuca geç."}
    if "html" not in r.headers.get("Content-Type", "html"):
        return {"hata": "Bu adres bir web sayfası değil (dosya olabilir)."}
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    p = _TextExtractor()
    try:
        p.feed(r.text)
    except Exception:
        pass
    text = p.text()
    if len(text) < 200:
        return {"hata": "Sayfadan okunabilir yazı çıkmadı (site içeriği sonradan yüklüyor olabilir). Başka bir sonuca geç.",
                "başlık": p.title.strip()}
    LIMIT = 5000
    start = int(baslangic or 0)
    if odak and not baslangic:
        i = _norm(text).find(_norm(odak))
        if i > 0:
            start = max(0, i - 300)
    chunk = text[start:start + LIMIT]
    res = {"başlık": p.title.strip(), "adres": r.url, "metin": chunk}
    if start + LIMIT < len(text):
        res["devamı_var"] = f"Sayfanın devamı için sayfa_oku'yu baslangic={start + LIMIT} ile tekrar çağır."
    return res


# --------------------------- YouTube ---------------------------

def _walk(obj, key):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield v
            else:
                yield from _walk(v, key)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v, key)


def _txt(o):
    if not isinstance(o, dict):
        return ""
    if "simpleText" in o:
        return o["simpleText"]
    return "".join(r.get("text", "") for r in o.get("runs", []))


def youtube_ara(arama: str, adet: int = 8):
    import re
    import json as _json
    import requests
    from urllib.parse import quote_plus
    try:
        r = requests.get("https://www.youtube.com/results?search_query=" + quote_plus(arama),
                         headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                                "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
                                  "Accept-Language": "tr-TR,tr;q=0.9"},
                         cookies={"CONSENT": "YES+1"}, timeout=15)
        m = re.search(r"var ytInitialData\s*=\s*(\{.*?\});\s*</script>", r.text, re.S)
        if not m:
            return {"hata": "YouTube sonuçları okunamadı."}
        data = _json.loads(m.group(1))
    except Exception as e:
        return {"hata": f"YouTube'a ulaşılamadı: {e}"}
    out = []
    for v in _walk(data, "videoRenderer"):
        if not v.get("videoId"):
            continue
        out.append({
            "video_id": v["videoId"],
            "başlık": _txt(v.get("title")),
            "kanal": _txt(v.get("ownerText")),
            "süre": _txt(v.get("lengthText")) or "canlı/bilinmiyor",
            "izlenme": _txt(v.get("viewCountText")),
            "yayın": _txt(v.get("publishedTimeText")),
        })
        if len(out) >= int(adet):
            break
    return {"arama": arama, "sonuçlar": out,
            "not": "Kullanıcının isteğine en uygun videoyu seç, kısaca nedenini söyle, sonra youtube_ac ile video_id'yi aç."}


def youtube_ac(video_id: str = "", arama: str = ""):
    from urllib.parse import quote_plus
    if video_id:
        url = "https://www.youtube.com/watch?v=" + video_id
    elif arama:
        url = "https://www.youtube.com/results?search_query=" + quote_plus(arama)
    else:
        url = "https://www.youtube.com/"
    lnk = _open_in_web_app("YouTube", url)
    if lnk:
        return {"tamam": "YouTube UYGULAMASINDA açıldı.", "adres": url}
    webbrowser.open(url)
    return {"tamam": "YouTube uygulaması bulunamadı, varsayılan TARAYICIDA açıldı.", "adres": url}


def gecici_dosya_boyutu():
    tmp = Path(os.environ.get("TEMP", "/tmp"))
    total, count = 0, 0
    for dirpath, _, files in os.walk(tmp):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
                count += 1
            except Exception:
                pass
    return {"klasör": str(tmp), "dosya_sayısı": count, "toplam_boyut": _fmt_size(total)}


def calisan_programlar(adet: int = 15):
    procs = []
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            procs.append((p.info["memory_info"].rss, p.info["name"]))
        except Exception:
            pass
    merged = {}
    for rss, name in procs:
        merged[name] = merged.get(name, 0) + rss
    top = sorted(merged.items(), key=lambda x: -x[1])[: int(adet)]
    return {"en_çok_ram_kullananlar": [{"program": n, "ram": _fmt_size(r)} for n, r in top]}


# ----------------------------------------------------------------------------
# SARI araçlar (onay ister)
# ----------------------------------------------------------------------------

def dosya_sil(yollar: list):
    if send2trash is None:
        return {"hata": "send2trash kurulu değil."}
    done, errors = [], []
    for y in yollar:
        p = Path(y)
        if _is_protected(p):
            errors.append(f"{y}: korumalı konum, dokunmadım")
            continue
        try:
            send2trash(str(p))
            done.append(y)
        except Exception as e:
            errors.append(f"{y}: {e}")
    return {"geri_dönüşüme_atılan": done, "hatalar": errors,
            "not": "Dosyalar Geri Dönüşüm Kutusu'nda, istenirse geri alınabilir."}


def dosya_tasi(yollar: list, hedef: str):
    dest = _known_folder(hedef)
    dest.mkdir(parents=True, exist_ok=True)
    done, errors = [], []
    for y in yollar:
        p = Path(y)
        if _is_protected(p):
            errors.append(f"{y}: korumalı konum")
            continue
        try:
            shutil.move(str(p), str(dest / p.name))
            done.append(y)
        except Exception as e:
            errors.append(f"{y}: {e}")
    return {"taşınan": done, "hedef": str(dest), "hatalar": errors}


def uygulama_kaldir(ad: str):
    if not IS_WINDOWS:
        return {"hata": "Bu araç sadece Windows'ta çalışır."}
    apps = _registry_apps()
    match = [a for a in apps if a["ad"].lower() == ad.lower()] or \
            [a for a in apps if ad.lower() in a["ad"].lower()]
    if not match:
        return {"hata": f"'{ad}' adında uygulama bulamadım."}
    if len(match) > 1:
        return {"hata": "Birden fazla eşleşme var, tam adı söyle.", "eşleşenler": [a["ad"] for a in match]}
    app = match[0]
    if not app["_kaldir"]:
        return {"hata": "Bu uygulamanın kaldırma komutu yok, Ayarlar > Uygulamalar'dan kaldırılmalı."}
    try:
        subprocess.Popen(app["_kaldir"], shell=True)
        return {"tamam": f"'{app['ad']}' kaldırıcısı başlatıldı. Açılan pencere varsa oradan devam et."}
    except Exception as e:
        return {"hata": str(e)}


def gecici_dosyalari_temizle():
    tmp = Path(os.environ.get("TEMP", "/tmp"))
    freed, skipped = 0, 0
    for item in tmp.iterdir():
        try:
            size = item.stat().st_size if item.is_file() else sum(
                f.stat().st_size for f in item.rglob("*") if f.is_file())
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            freed += size
        except Exception:
            skipped += 1  # kullanımda olan dosyalar atlanır, normal
    return {"açılan_alan": _fmt_size(freed), "atlanan(kullanımda)": skipped}


# ----------------------------------------------------------------------------
# Kayıt: hangi araç hangi seviyede, model için açıklamaları
# ----------------------------------------------------------------------------

def _t(name, desc, props=None, required=None):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props or {}, "required": required or []}}}


_KLASOR = {"type": "string", "description": "Klasör: 'masaüstü', 'indirilenler', 'belgeler', 'resimler', 'videolar', 'ev' ya da tam yol"}
_YOLLAR = {"type": "array", "items": {"type": "string"}, "description": "Dosya/klasörlerin tam yolları"}

TOOLS = [
    _t("sistem_bilgisi", "İşlemci, RAM ve disk doluluk bilgisini verir."),
    _t("klasor_listele", "Bir klasördeki dosya ve klasörleri listeler.", {"klasor": _KLASOR, "adet": {"type": "integer"}}),
    _t("dosya_ara", "Dosya adına göre arar. Örn desen: 'fatura', '*.pdf'.", {"desen": {"type": "string"}, "klasor": _KLASOR}, ["desen"]),
    _t("buyuk_dosyalar", "Bir klasördeki en büyük dosyaları bulur.", {"klasor": _KLASOR, "adet": {"type": "integer"}}),
    _t("uygulamalari_listele", "Bilgisayarda kurulu uygulamaları listeler (ad, yayıncı, kurulum tarihi, boyut)."),
    _t("uygulama_ac", "Bir programı ya da görev çubuğu/başlat menüsündeki uygulamayı açar. Örn: 'chrome', 'spotify', 'YouTube', 'WhatsApp'.", {"ad": {"type": "string"}}, ["ad"]),
    _t("web_ac", "Varsayılan TARAYICIDA bir web sitesi açar. YouTube için bunu değil youtube_ac'ı kullan.", {"adres": {"type": "string"}}, ["adres"]),
    _t("ses_medya", "Ses ve medya kontrolü. islem: 'ac'/'kis' (deger=yüzde kadar), 'yuzde' (deger=hedef ses), 'sessiz', 'oynat' (durdur/devam), 'sonraki', 'onceki', 'kilitle' (bilgisayarı kilitler).", {"islem": {"type": "string", "enum": ["ac", "kis", "yuzde", "sessiz", "oynat", "sonraki", "onceki", "kilitle"]}, "deger": {"type": "integer"}}, ["islem"]),
    _t("zamanli_kapat", "Bilgisayarı belirtilen dakika sonra kapatır (onay otomatik istenir). iptal=true ise ayarlı kapatmayı iptal eder.", {"dakika": {"type": "integer"}, "iptal": {"type": "boolean"}}),
    _t("not_kaydet", "Yazıyı yeni bir .txt dosyasına kaydeder ve Not Defteri'nde açar. Var olan dosyanın üstüne yazmaz. 'icerik' tam ve düzenli metin olmalı.", {"baslik": {"type": "string", "description": "Dosya adı, örn 'Süper Lig puan durumu'"}, "icerik": {"type": "string"}, "klasor": _KLASOR, "ac": {"type": "boolean"}}, ["baslik", "icerik"]),
    _t("web_ara", "İnternette arama yapar; başlık, adres ve kısa özet döner. Güncel bilgi (puan durumu, fikstür, haber, fiyat, hava) için ilk adım.", {"arama": {"type": "string"}, "adet": {"type": "integer"}}, ["arama"]),
    _t("sayfa_oku", "Bir web sayfasına girip yazısını ve tablolarını okur. 'odak' verilirse sayfanın o kelimenin geçtiği kısmından başlar. Uzun sayfalarda 'baslangic' ile devamını okursun.", {"adres": {"type": "string"}, "odak": {"type": "string", "description": "Sayfada aranacak kelime, örn 'Puan durumu'"}, "baslangic": {"type": "integer"}}, ["adres"]),
    _t("youtube_ara", "YouTube'da arama yapar, ilk sonuçların başlık, kanal, süre ve izlenmesini döner. Video açmaz.", {"arama": {"type": "string"}, "adet": {"type": "integer"}}, ["arama"]),
    _t("youtube_ac", "YouTube'u kullanıcının YouTube uygulamasında açar (yoksa tarayıcıda). video_id verilirse o videoyu, arama verilirse arama sonuçlarını açar.", {"video_id": {"type": "string"}, "arama": {"type": "string"}}),
    _t("gecici_dosya_boyutu", "Geçici (temp) dosyaların ne kadar yer kapladığını söyler."),
    _t("calisan_programlar", "En çok RAM kullanan çalışan programları listeler.", {"adet": {"type": "integer"}}),
    _t("dosya_sil", "Dosyaları Geri Dönüşüm Kutusu'na atar. (Kullanıcı onayı otomatik istenir.)", {"yollar": _YOLLAR}, ["yollar"]),
    _t("dosya_tasi", "Dosyaları başka klasöre taşır. (Onay otomatik istenir.)", {"yollar": _YOLLAR, "hedef": _KLASOR}, ["yollar", "hedef"]),
    _t("uygulama_kaldir", "Kurulu bir uygulamanın kaldırıcısını başlatır. (Onay otomatik istenir.)", {"ad": {"type": "string"}}, ["ad"]),
    _t("gecici_dosyalari_temizle", "Geçici dosyaları siler. (Onay otomatik istenir.)"),
]

_FUNCS = {
    "sistem_bilgisi": sistem_bilgisi, "klasor_listele": klasor_listele, "dosya_ara": dosya_ara,
    "buyuk_dosyalar": buyuk_dosyalar, "uygulamalari_listele": uygulamalari_listele,
    "uygulama_ac": uygulama_ac, "web_ac": web_ac, "gecici_dosya_boyutu": gecici_dosya_boyutu,
    "youtube_ara": youtube_ara, "youtube_ac": youtube_ac,
    "web_ara": web_ara, "sayfa_oku": sayfa_oku, "not_kaydet": not_kaydet,
    "ses_medya": ses_medya, "zamanli_kapat": zamanli_kapat,
    "calisan_programlar": calisan_programlar, "dosya_sil": dosya_sil, "dosya_tasi": dosya_tasi,
    "uygulama_kaldir": uygulama_kaldir, "gecici_dosyalari_temizle": gecici_dosyalari_temizle,
}

ONAYLI = {"dosya_sil", "dosya_tasi", "uygulama_kaldir", "gecici_dosyalari_temizle", "zamanli_kapat"}

_STATUS = {
    "sistem_bilgisi": "Sistem bilgilerine bakıyorum", "klasor_listele": "Klasöre bakıyorum",
    "dosya_ara": "Dosya arıyorum", "buyuk_dosyalar": "Büyük dosyaları tarıyorum",
    "uygulamalari_listele": "Uygulamaları tarıyorum", "uygulama_ac": "Program açıyorum",
    "web_ac": "Siteyi açıyorum", "gecici_dosya_boyutu": "Geçici dosyaları ölçüyorum",
    "calisan_programlar": "Çalışan programlara bakıyorum",
    "youtube_ara": "YouTube'da arıyorum", "youtube_ac": "YouTube'u açıyorum",
    "web_ara": "İnternette arıyorum", "sayfa_oku": "Sayfayı okuyorum", "not_kaydet": "Not defterine yazıyorum",
}


def status_text(name):
    return _STATUS.get(name, "Çalışıyorum")


def describe_action(name, args):
    """Onay kartında gösterilecek başlık ve detay."""
    if name == "dosya_sil":
        y = args.get("yollar", [])
        return {"baslik": f"{len(y)} öğe Geri Dönüşüm Kutusu'na atılacak", "detay": y}
    if name == "dosya_tasi":
        y = args.get("yollar", [])
        return {"baslik": f"{len(y)} öğe '{args.get('hedef')}' klasörüne taşınacak", "detay": y}
    if name == "uygulama_kaldir":
        return {"baslik": "Uygulama kaldırılacak", "detay": [args.get("ad", "?")]}
    if name == "zamanli_kapat":
        if args.get("iptal"):
            return {"baslik": "Zamanlı kapatma iptal edilecek", "detay": []}
        return {"baslik": f"Bilgisayar {args.get('dakika', '?')} dakika sonra kapanacak", "detay": ["Açık işlerini kaydetmeyi unutma"]}
    if name == "gecici_dosyalari_temizle":
        return {"baslik": "Geçici dosyalar silinecek", "detay": ["Kullanımda olanlar atlanır"]}
    return {"baslik": name, "detay": [str(args)]}


def run_tool(name, args):
    fn = _FUNCS.get(name)
    if not fn:
        return {"hata": f"'{name}' diye bir aracım yok."}
    try:
        return fn(**(args or {}))
    except TypeError as e:
        return {"hata": f"Yanlış parametre: {e}"}
    except Exception as e:
        return {"hata": str(e)}
