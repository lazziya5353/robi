"""
Güvenilir hazır bilgi kaynakları (sayfa kazımak yerine resmi/ücretsiz servisler):
- Döviz: TCMB günlük kurlar (yedek: open.er-api.com)
- Hava: Open-Meteo (anahtar gerektirmez)
- Haber: ddgs haber araması, tarih filtreli
"""
import xml.etree.ElementTree as ET

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Robi/1.0"}


# ---------------- döviz ----------------

def doviz_kuru(birimler: list = None):
    birimler = [b.upper() for b in (birimler or ["USD", "EUR", "GBP"])]
    try:
        r = requests.get("https://www.tcmb.gov.tr/kurlar/today.xml", headers=UA, timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        out = {}
        for c in root.findall("Currency"):
            code = c.get("CurrencyCode") or c.get("Kod")
            if code in birimler:
                unit = int(c.findtext("Unit") or 1)
                al, sat = c.findtext("ForexBuying"), c.findtext("ForexSelling")
                out[code] = {"ad": c.findtext("Isim"), "alış": float(al) / unit if al else None,
                             "satış": float(sat) / unit if sat else None}
        if out:
            return {"kaynak": "TCMB (Merkez Bankası)", "tarih": root.get("Tarih"), "kurlar_TL": out,
                    "not": "TCMB kurları günde bir kez (15.30) açıklanır; piyasadaki anlık kur biraz farklı olabilir. "
                           "Hafta sonu/tatilde son iş gününün kuru gösterilir."}
    except Exception:
        pass
    try:  # yedek
        r = requests.get("https://open.er-api.com/v6/latest/TRY", headers=UA, timeout=10).json()
        rates = r.get("rates", {})
        out = {b: {"satış": round(1 / rates[b], 4)} for b in birimler if rates.get(b)}
        return {"kaynak": "open.er-api.com", "güncelleme": r.get("time_last_update_utc"), "kurlar_TL": out}
    except Exception as e:
        return {"hata": f"Kur bilgisi alınamadı: {e}"}


# ---------------- hava ----------------

_WMO = {0: "açık", 1: "çoğunlukla açık", 2: "parçalı bulutlu", 3: "kapalı", 45: "sisli", 48: "kırağılı sis",
        51: "hafif çisenti", 53: "çisenti", 55: "yoğun çisenti", 61: "hafif yağmurlu", 63: "yağmurlu",
        65: "şiddetli yağmur", 66: "dondurucu yağmur", 67: "şiddetli dondurucu yağmur", 71: "hafif kar",
        73: "karlı", 75: "yoğun kar", 77: "kar taneli", 80: "hafif sağanak", 81: "sağanak", 82: "şiddetli sağanak",
        85: "kar sağanağı", 86: "yoğun kar sağanağı", 95: "gök gürültülü fırtına", 96: "dolu ihtimalli fırtına",
        99: "şiddetli dolu fırtınası"}


def hava_durumu(sehir: str = "İstanbul", gun: int = 3):
    try:
        g = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                         params={"name": sehir, "count": 1, "language": "tr"}, headers=UA, timeout=10).json()
        if not g.get("results"):
            return {"hata": f"'{sehir}' diye bir yer bulamadım."}
        p = g["results"][0]
        f = requests.get("https://api.open-meteo.com/v1/forecast", headers=UA, timeout=10, params={
            "latitude": p["latitude"], "longitude": p["longitude"], "timezone": "auto",
            "forecast_days": max(1, min(int(gun), 7)),
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"}).json()
        c, d = f.get("current", {}), f.get("daily", {})
        gunler = [{"tarih": d["time"][i], "durum": _WMO.get(d["weather_code"][i], "?"),
                   "en_yüksek": d["temperature_2m_max"][i], "en_düşük": d["temperature_2m_min"][i],
                   "yağış_ihtimali_%": d["precipitation_probability_max"][i]} for i in range(len(d.get("time", [])))]
        yer = p["name"] if p.get("admin1") in (None, "", p["name"]) else f"{p['name']}, {p['admin1']}"
        return {"yer": yer, "kaynak": "Open-Meteo",
                "şu_an": {"sıcaklık": c.get("temperature_2m"), "hissedilen": c.get("apparent_temperature"),
                          "nem_%": c.get("relative_humidity_2m"), "rüzgar_kmh": c.get("wind_speed_10m"),
                          "durum": _WMO.get(c.get("weather_code"), "?")},
                "günler": gunler}
    except Exception as e:
        return {"hata": f"Hava durumu alınamadı: {e}"}


# ---------------- haber ----------------

_ZAMAN = {"gun": "d", "gün": "d", "bugun": "d", "bugün": "d", "hafta": "w", "ay": "m", "yil": "y", "yıl": "y"}


def haber_ara(konu: str, zaman: str = "hafta", adet: int = 10):
    """Son günlerin haberlerini tarihleriyle getirir."""
    try:
        from ddgs import DDGS
        res = DDGS(timeout=10).news(konu, region="tr-tr", safesearch="moderate",
                                    timelimit=_ZAMAN.get(str(zaman).lower(), "w"), max_results=int(adet))
    except Exception as e:
        return {"hata": f"Haber araması yapılamadı: {e}"}
    out = [{"tarih": (n.get("date") or "")[:10], "başlık": n.get("title"), "kaynak": n.get("source"),
            "özet": (n.get("body") or "")[:300], "adres": n.get("url")} for n in res]
    if not out:
        return {"sonuç": "Bu zaman aralığında haber bulunamadı. Zamanı genişlet ya da farklı kelimelerle dene."}
    return {"konu": konu, "zaman": zaman, "haberler": out,
            "not": "Önemli haberlerin detayı için sayfa_oku kullanabilirsin. Cevapta tarih ve kaynak adı belirt, link yazma."}
