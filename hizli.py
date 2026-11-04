"""
Hızlı komutlar: basit ve net komutlar yapay zekâyı hiç çalıştırmadan anında yapılır.
Eşleşmeyen her şey normal şekilde beyne gider.
"""
import re
import subprocess
import sys

IS_WINDOWS = sys.platform.startswith("win")
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Windows medya tuşları
VK = {"ses_ac": 0xAF, "ses_kis": 0xAE, "sessiz": 0xAD, "oynat": 0xB3, "sonraki": 0xB0, "onceki": 0xB1}


def _press(vk, times=1):
    if not IS_WINDOWS:
        raise RuntimeError("Bu komut sadece Windows'ta çalışır")
    import ctypes
    for _ in range(times):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)


# ---------------- işlemler (tools.py de bunları kullanır) ----------------

def ses(islem: str, deger: int = 10):
    """islem: ac | kis | sessiz | yuzde. Her tuş basışı Windows'ta %2."""
    if islem == "ac":
        _press(VK["ses_ac"], max(1, deger // 2))
        return f"🔊 Sesi %{deger} açtım."
    if islem == "kis":
        _press(VK["ses_kis"], max(1, deger // 2))
        return f"🔉 Sesi %{deger} kıstım."
    if islem == "sessiz":
        _press(VK["sessiz"])
        return "🔇 Sesi kapattım/açtım (sessiz modu değiştirdim)."
    if islem == "yuzde":
        deger = max(0, min(100, int(deger)))
        _press(VK["ses_kis"], 50)
        _press(VK["ses_ac"], deger // 2)
        return f"🔊 Sesi %{deger} yaptım."
    raise ValueError("bilinmeyen ses işlemi")


def medya(islem: str):
    """islem: oynat | sonraki | onceki"""
    _press(VK[islem])
    return {"oynat": "⏯️ Müziği durdurdum/devam ettirdim.", "sonraki": "⏭️ Sonraki şarkıya geçtim.",
            "onceki": "⏮️ Önceki şarkıya döndüm."}[islem]


def kilitle():
    import ctypes
    ctypes.windll.user32.LockWorkStation()
    return "🔒 Bilgisayarı kilitledim."


def zamanli_kapat(dakika: int):
    subprocess.run(["shutdown", "/s", "/t", str(int(dakika) * 60)], creationflags=_NO_WINDOW, check=True)
    if dakika >= 60 and dakika % 60 == 0:
        t = f"{dakika // 60} saat"
    else:
        t = f"{dakika} dakika"
    return f"⏲️ Tamam, bilgisayar {t} sonra kapanacak. Vazgeçersen \"kapatmayı iptal et\" yaz."


def kapatma_iptal():
    r = subprocess.run(["shutdown", "/a"], creationflags=_NO_WINDOW, capture_output=True)
    return "✅ Zamanlı kapatmayı iptal ettim." if r.returncode == 0 else "Zaten ayarlı bir kapatma yoktu."


# ---------------- eşleştirme ----------------

def _norm(t: str) -> str:
    t = t.strip().lower().replace("İ", "i").replace("I", "ı")
    t = re.sub(r"[.!?,]+$", "", t)
    return re.sub(r"\s+", " ", t)


_SUFFIX = re.compile(r"(['’]?(y[ıiuü]|n[ıiuü]|[ıiuü]))$")


def _app_candidates(raw: str):
    raw = raw.strip()
    yield raw.replace("'", "").replace("’", "")
    if "'" in raw or "’" in raw:
        yield re.split(r"['’]", raw)[0]
    stripped = _SUFFIX.sub("", raw)
    if stripped and stripped != raw:
        yield stripped


def eslestir(text: str):
    """Eşleşirse {'yap': fonksiyon, 'onay': (varsa onay kartı)} döner, yoksa None."""
    t = _norm(text)
    if len(t) > 60:
        return None

    # --- ses ---
    m = re.fullmatch(r"ses(?:i)? (?:%|yüzde ?)(\d{1,3})(?: ?(?:yap|ayarla|olsun))?", t) or \
        re.fullmatch(r"ses(?:i)? (\d{1,3}) ?(?:yap|ayarla|olsun)", t)
    if m:
        v = int(m.group(1))
        return {"yap": lambda: ses("yuzde", v)}
    if re.fullmatch(r"ses(?:i)? (?:biraz |az )?(?:kıs|azalt|düşür)", t):
        return {"yap": lambda: ses("kis", 10)}
    if re.fullmatch(r"ses(?:i)? (?:çok )?(?:kıs|azalt|düşür) ?çok", t) or t == "sesi çok kıs":
        return {"yap": lambda: ses("kis", 30)}
    if re.fullmatch(r"ses(?:i)? (?:biraz |az )?(?:aç|artır|yükselt)", t):
        return {"yap": lambda: ses("ac", 10)}
    if t in ("sesi çok aç", "sesi çok artır"):
        return {"yap": lambda: ses("ac", 30)}
    if re.fullmatch(r"(?:ses(?:i)? (?:kapat|sustur)|sessize al|sessiz(?: mod)?)", t):
        return {"yap": lambda: ses("sessiz")}

    # --- medya ---
    if re.fullmatch(r"(?:müziği |şarkıyı |videoyu )?(?:durdur|duraklat|devam et|oynat|başlat)", t) and t != "başlat":
        return {"yap": lambda: medya("oynat")}
    if re.fullmatch(r"(?:sonraki|sıradaki) (?:şarkı|parça)(?:ya geç)?|şarkıyı geç|sonrakine geç", t):
        return {"yap": lambda: medya("sonraki")}
    if re.fullmatch(r"önceki (?:şarkı|parça)(?:ya dön)?|öncekine dön", t):
        return {"yap": lambda: medya("onceki")}

    # --- güç ---
    if re.fullmatch(r"(?:bilgisayarı |pc'?yi |ekranı )?kilitle", t):
        return {"yap": kilitle}
    m = re.fullmatch(r"(?:bilgisayarı |pc'?yi )?(\d{1,4}) ?(dakika|dk|saat|sa) sonra kapat", t)
    if m:
        dk = int(m.group(1)) * (60 if m.group(2) in ("saat", "sa") else 1)
        sure = f"{m.group(1)} {'saat' if dk >= 60 and m.group(2) in ('saat', 'sa') else 'dakika'}"
        return {"yap": lambda: zamanli_kapat(dk),
                "onay": {"baslik": f"Bilgisayar {sure} sonra kapanacak", "detay": ["Açık işlerini kaydetmeyi unutma"]}}
    if re.fullmatch(r"(?:bilgisayarı )?(?:kapatmayı|kapanmayı|kapanışı) iptal(?: et)?", t):
        return {"yap": kapatma_iptal}

    # --- uygulama aç: "chrome'u aç", "spotify aç", "discordu aç" ---
    m = re.fullmatch(r"(.{2,30}?) (?:aç|başlat)", t)
    if m and not re.search(r"(?:'?[dt][ae]|'?[dt][ae]n|ile|için|ve|bir)\b", m.group(1)):
        import tools
        for cand in _app_candidates(m.group(1)):
            if cand in ("youtube", "yt"):
                return {"yap": lambda: _say(tools.youtube_ac(), "YouTube")}
            if len(cand) < 3:
                continue
            found = tools._find_shortcut(cand) if IS_WINDOWS else None
            if found or cand in tools._APP_ALIASES:
                return {"yap": (lambda c=cand: _say(tools.uygulama_ac(c), c))}
    return None


def _say(res: dict, name: str):
    if "hata" in res:
        return res["hata"]
    return f"✅ {name[:1].upper() + name[1:]} açılıyor." if "kisayol" in res or "açılıyor" in res.get("tamam", "") \
        else "✅ " + res.get("tamam", "Tamam.")
