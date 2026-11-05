"""
Çalışma programı: belirli saat ve günlerde Robi'ye otomatik iş yaptırma.
- tur "gorev": komut Robi'ye verilir (ben yokken modunda), sonunda rapor hazırlanır, Telegram'a gider
- tur "hatirlatma": yapay zekâ kullanılmaz, sadece mesaj gösterilir/gönderilir
Program sadece bu bilgisayarda durur (program.json), GitHub'a gitmez.
"""
import json
import re
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
FILE = BASE / "program.json"
_LOCK = threading.Lock()

GUN_AD = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
_GUN_ALIAS = {
    "pazartesi": 0, "pzt": 0, "salı": 1, "sali": 1, "sal": 1, "çarşamba": 2, "carsamba": 2, "çar": 2, "car": 2,
    "perşembe": 3, "persembe": 3, "per": 3, "cuma": 4, "cum": 4, "cumartesi": 5, "cmt": 5, "pazar": 6, "paz": 6,
}


def _load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items):
    FILE.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def gunleri_coz(gunler) -> list:
    """'her gün', 'hafta içi', 'hafta sonu', ['pazartesi','cuma'], [0,4] → [0..6] listesi."""
    if gunler is None or gunler == "" or gunler == []:
        return list(range(7))
    if isinstance(gunler, str):
        t = gunler.lower().strip()
        if t in ("her gün", "her gun", "hergün", "günlük", "gunluk", "her", "hepsi"):
            return list(range(7))
        if "hafta içi" in t or "hafta ici" in t or "hafta-içi" in t:
            return [0, 1, 2, 3, 4]
        if "hafta sonu" in t or "haftasonu" in t:
            return [5, 6]
        gunler = re.split(r"[,\s]+(?:ve\s+)?", t)
    out = set()
    for g in gunler:
        if isinstance(g, int) and 0 <= g <= 6:
            out.add(g)
        elif isinstance(g, str) and g.strip():
            tok = g.lower().strip().replace("'", "")
            # en uzun eşleşen gün adı: "cumartesi" cuma değil cumartesi, "pazarları" pazar olur
            hits = [n for n in _GUN_ALIAS if tok == n or tok.startswith(n)]
            if hits:
                out.add(_GUN_ALIAS[max(hits, key=len)])
    return sorted(out) or list(range(7))


def saati_coz(saat: str) -> str:
    """'9', '09:00', '9.30', '21:15' → 'HH:MM'"""
    m = re.fullmatch(r"\s*(\d{1,2})(?:[:.](\d{2}))?\s*", str(saat))
    if not m or int(m.group(1)) > 23 or int(m.group(2) or 0) > 59:
        raise ValueError("Saat 'SS:DD' biçiminde olmalı, örn 09:00")
    return f"{int(m.group(1)):02d}:{int(m.group(2) or 0):02d}"


def ekle(ad: str, komut: str, saat: str, gunler=None, tur: str = "gorev", tarih: str = "", rapor: bool = True):
    try:
        saat = saati_coz(saat)
    except ValueError as e:
        return {"hata": str(e)}
    komut = (komut or "").strip()
    if not komut:
        return {"hata": "Ne yapılacağı (komut) boş olamaz."}
    if tarih:
        try:
            datetime.strptime(tarih, "%Y-%m-%d")
        except ValueError:
            return {"hata": "Tarih YYYY-AA-GG biçiminde olmalı, örn 2026-11-06"}
    now = datetime.now()
    if tarih and (tarih < now.strftime("%Y-%m-%d") or (tarih == now.strftime("%Y-%m-%d") and saat <= now.strftime("%H:%M"))):
        return {"hata": f"{tarih} {saat} geçmiş bir zaman. İleri bir saat ya da tarih ver."}
    item = {"id": uuid.uuid4().hex[:6], "ad": (ad or komut[:40]).strip()[:60], "komut": komut[:2000], "saat": saat,
            "gunler": gunleri_coz(gunler), "tur": "hatirlatma" if tur == "hatirlatma" else "gorev",
            "tarih": tarih or "", "rapor": bool(rapor), "aktif": True, "son": ""}
    if not tarih and saat <= now.strftime("%H:%M"):
        item["son"] = now.strftime("%Y-%m-%d")  # bugünün saati geçtiyse yarından başlasın, hemen çalışmasın
    with _LOCK:
        items = _load()
        items.append(item)
        _save(items)
    return {"tamam": "Programa eklendi.", "gorev": ozet(item)}


def liste():
    return _load()


def ozet(it) -> str:
    if it.get("tarih"):
        ne_zaman = f"{it['tarih']} {it['saat']} (tek sefer)"
    elif len(it["gunler"]) == 7:
        ne_zaman = f"her gün {it['saat']}"
    elif it["gunler"] == [0, 1, 2, 3, 4]:
        ne_zaman = f"hafta içi {it['saat']}"
    elif it["gunler"] == [5, 6]:
        ne_zaman = f"hafta sonu {it['saat']}"
    else:
        ne_zaman = ", ".join(GUN_AD[g] for g in it["gunler"]) + f" {it['saat']}"
    tip = "⏰ hatırlatma" if it["tur"] == "hatirlatma" else "📋 görev"
    durum = "" if it.get("aktif", True) else " (durduruldu)"
    return f"{tip} · {it['ad']} · {ne_zaman}{durum}"


def bul(ad_veya_id: str):
    q = (ad_veya_id or "").lower().strip()
    items = _load()
    return next((i for i in items if i["id"] == q), None) or \
        next((i for i in items if q and q in i["ad"].lower()), None)


def sil(ad_veya_id: str):
    it = bul(ad_veya_id)
    if not it:
        return {"hata": "Bu isimde bir program bulamadım."}
    with _LOCK:
        _save([i for i in _load() if i["id"] != it["id"]])
    return {"tamam": f"Silindi: {it['ad']}"}


def ayarla(item_id: str, **degisiklik):
    with _LOCK:
        items = _load()
        for i in items:
            if i["id"] == item_id:
                for k in ("aktif", "rapor", "ad", "komut", "saat", "gunler"):
                    if k in degisiklik:
                        v = degisiklik[k]
                        i[k] = saati_coz(v) if k == "saat" else gunleri_coz(v) if k == "gunler" else v
        _save(items)
    return True


def zamani_gelenler(now: datetime = None):
    """Şu an çalışması gerekenler. Bilgisayar o saatte kapalıysa aynı gün içinde sonradan bir kez çalışır."""
    now = now or datetime.now()
    today = now.strftime("%Y-%m-%d")
    hhmm = now.strftime("%H:%M")
    due = []
    for it in _load():
        if not it.get("aktif", True) or it.get("son") == today:
            continue
        if it.get("tarih"):
            if it["tarih"] != today:
                continue
        elif now.weekday() not in it["gunler"]:
            continue
        if hhmm >= it["saat"]:
            due.append(it)
    return due


def calisti(item_id: str, now: datetime = None):
    now = now or datetime.now()
    with _LOCK:
        items = _load()
        for i in items:
            if i["id"] == item_id:
                i["son"] = now.strftime("%Y-%m-%d")
                if i.get("tarih"):  # tek seferlik görev bitti
                    i["aktif"] = False
        _save(items)


def siradaki(now: datetime = None):
    """Bir sonraki çalışma zamanı (gösterim için)."""
    now = now or datetime.now()
    best = None
    for it in _load():
        if not it.get("aktif", True):
            continue
        for d in range(8):
            day = now + timedelta(days=d)
            if it.get("tarih") and it["tarih"] != day.strftime("%Y-%m-%d"):
                continue
            if not it.get("tarih") and day.weekday() not in it["gunler"]:
                continue
            h, m = map(int, it["saat"].split(":"))
            t = day.replace(hour=h, minute=m, second=0, microsecond=0)
            if t < now or (d == 0 and it.get("son") == now.strftime("%Y-%m-%d")):
                continue
            if best is None or t < best[0]:
                best = (t, it)
            break
    return best
