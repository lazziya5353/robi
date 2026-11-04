"""
Telegram bağlantısı: dışarıdayken telefondan Robi'ye iş ver, cevabı ve raporu telefona al.

Güvenlik:
- Bot token'ı ve eşleşen sohbet kimliği gizli.json'da durur (GitHub'a gitmez).
- Bot sadece eşleşme kodunu gönderen TEK kişiyi tanır; başka herkes yok sayılır.
- Silme/kaldırma/kapatma gibi işler Telegram'da ✅/❌ butonlarıyla onaylanır.
"""
import hashlib
import html
import io
import os
import json
import random
import re
import threading
import time
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
SECRET = BASE / "gizli.json"
API = "https://api.telegram.org/bot{token}/{method}"

YARDIM = ("🤖 **Robi burada.** Bana yazdığın her şeyi bilgisayarında yaparım.\n\n"
          "Örnekler:\n• Şampiyonlar Ligi puan durumunu araştır, Word'e yaz\n• Masaüstümde ne var?\n"
          "• İndirilenler'deki büyük dosyaları bul, rapor et\n\n"
          "Komutlar:\n/durum – şu an ne yapıyorum\n/durdur – işi durdur\n/onaylar – onay bekleyen işler\n"
          "/ekran – ekranın görüntüsü\n/yardim – bu mesaj")


def _secrets():
    try:
        return json.loads(SECRET.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_secret(**kw):
    d = _secrets()
    for k, v in kw.items():
        if v is None:
            d.pop(k, None)
        else:
            d[k] = v
    SECRET.write_text(json.dumps(d), encoding="utf-8")


def md_to_html(text: str) -> str:
    """Robi'nin markdown'ını Telegram HTML'ine çevirir; tabloları hizalı kod bloğu yapar."""
    lines, out, table = text.split("\n"), [], []

    def flush_table():
        if not table:
            return
        rows = [[c.strip().replace("**", "") for c in r.strip().strip("|").split("|")] for r in table
                if not re.fullmatch(r"\s*\|[\s:|-]+\|?\s*", r)]
        if rows:
            w = [max(len(r[i]) if i < len(r) else 0 for r in rows) for i in range(max(len(r) for r in rows))]
            body = "\n".join("  ".join((r[i] if i < len(r) else "").ljust(w[i]) for i in range(len(w))).rstrip() for r in rows)
            out.append("<pre>" + html.escape(body) + "</pre>")
        table.clear()

    for line in lines:
        if line.strip().startswith("|"):
            table.append(line)
            continue
        flush_table()
        t = html.escape(line)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"^#{1,3}\s+(.*)", r"<b>\1</b>", t)
        t = re.sub(r"^\s*[-*]\s+", "• ", t)
        out.append(t)
    flush_table()
    return "\n".join(out).strip()


class Telegram:
    def __init__(self, api):
        self.api = api              # app.Api
        self.pair_code = str(random.randint(100000, 999999))
        self.username = ""
        self.error = ""
        self._offset = 0
        self._waits = {}            # onay bekleyen: id -> {"event", "sonuc"}
        self._thread = None
        self._gen = 0               # token değişince eski döngü dursun
        self._pin_wait = None       # PIN bekleyen onay: {"kind": "c"|"p", "id", "tries"}
        self._lock_until = 0        # çok fazla yanlış PIN → telefondan onay kilitli

    # ---------------- durum ----------------
    @property
    def token(self):
        return _secrets().get("tg_token", "").strip()

    @property
    def chat_id(self):
        return _secrets().get("tg_chat_id")

    def paired(self):
        return bool(self.token and self.chat_id)

    def durum(self):
        if not self.token:
            return {"durum": "yok"}
        if self.error:
            return {"durum": "hata", "mesaj": self.error}
        if not self.chat_id:
            return {"durum": "eslesme", "kod": self.pair_code, "bot": self.username}
        return {"durum": "bagli", "bot": self.username, "pin": self.pin_var()}

    # ---------------- PIN (riskli işler için ikinci kilit) ----------------
    def pin_var(self):
        return bool(_secrets().get("tg_pin_hash"))

    @staticmethod
    def _hash(pin, salt):
        return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), 200_000).hex()

    def pin_kaydet(self, pin: str):
        pin = (pin or "").strip()
        if not (pin.isdigit() and 4 <= len(pin) <= 6):
            return {"hata": "PIN 4-6 haneli bir sayı olmalı."}
        salt = os.urandom(16).hex()
        _save_secret(tg_pin_salt=salt, tg_pin_hash=self._hash(pin, salt))
        return {"tamam": True}

    def pin_kaldir(self):
        _save_secret(tg_pin_salt=None, tg_pin_hash=None)
        return {"tamam": True}

    def _pin_dogru(self, pin: str) -> bool:
        d = _secrets()
        if not d.get("tg_pin_hash"):
            return True
        import hmac
        return hmac.compare_digest(self._hash(pin, d["tg_pin_salt"]), d["tg_pin_hash"])

    def _kilitli(self):
        return time.time() < self._lock_until

    # ---------------- ayarlar ----------------
    def kaydet(self, token: str):
        token = token.strip()
        try:
            r = requests.get(API.format(token=token, method="getMe"), timeout=10).json()
        except Exception as e:
            return {"durum": "hata", "mesaj": f"Telegram'a ulaşılamadı: {e}"}
        if not r.get("ok"):
            return {"durum": "hata", "mesaj": "Token geçersiz. BotFather'dan aldığın kodu tam kopyaladığından emin ol."}
        _save_secret(tg_token=token, tg_chat_id=None)
        self.username = r["result"].get("username", "")
        self.error = ""
        self.start()
        return self.durum()

    def kaldir(self):
        _save_secret(tg_token=None, tg_chat_id=None)
        self._gen += 1
        self.username = ""
        return self.durum()

    # ---------------- gönderme ----------------
    def _call(self, method, timeout=30, files=None, **params):
        url = API.format(token=self.token, method=method)
        if files:
            r = requests.post(url, data=params, files=files, timeout=timeout)
        else:
            r = requests.post(url, json=params, timeout=timeout)
        return r.json()

    def send(self, text: str, buttons=None, chat_id=None):
        chat_id = chat_id or self.chat_id
        if not (self.token and chat_id and text):
            return
        body = md_to_html(text)
        parts = [body[i:i + 3900] for i in range(0, len(body), 3900)] or [""]
        for i, part in enumerate(parts):
            params = {"chat_id": chat_id, "text": part, "parse_mode": "HTML", "disable_web_page_preview": True}
            if buttons and i == len(parts) - 1:
                params["reply_markup"] = {"inline_keyboard": buttons}
            try:
                r = self._call("sendMessage", **params)
                if not r.get("ok"):  # HTML bozuksa düz metin dene
                    params.pop("parse_mode")
                    params["text"] = re.sub(r"<[^>]+>", "", part)
                    self._call("sendMessage", **params)
            except Exception:
                pass

    def send_file(self, path, caption=""):
        if not self.paired():
            return
        try:
            with open(path, "rb") as f:
                self._call("sendDocument", timeout=120, files={"document": (Path(path).name, f)},
                           chat_id=self.chat_id, caption=caption[:1000])
        except Exception:
            pass

    def send_photo(self, png: bytes, caption=""):
        try:
            self._call("sendPhoto", timeout=120, files={"photo": ("ekran.png", png)}, chat_id=self.chat_id, caption=caption)
        except Exception:
            pass

    def send_pending(self, items):
        for it in items:
            detay = ", ".join(map(str, it.get("detay", [])))[:300]
            self.send(f"⏳ **Onay bekliyor:** {it['baslik']}\n{detay}",
                      buttons=[[{"text": "✅ Onayla", "callback_data": f"p:{it['id']}:1"},
                                {"text": "❌ İptal", "callback_data": f"p:{it['id']}:0"}]])

    # ---------------- Telegram'dan onay ----------------
    def ask(self, info, timeout=900) -> bool:
        """Onay kartını telefona gönderir, cevabı bekler (15 dk içinde cevap yoksa 'hayır')."""
        if self._kilitli():
            self.send("🔒 Çok fazla yanlış PIN girildiği için telefondan onay 15 dakika kapalı. Bu işlemi yapmadım.")
            return False
        wid = str(random.randint(10000, 99999))
        ev = threading.Event()
        self._waits[wid] = {"event": ev, "sonuc": False}
        detay = "\n".join(f"• {d}" for d in info.get("detay", [])[:15])
        if self.pin_var():
            self._pin_wait = {"kind": "c", "id": wid, "tries": 0}
            self.send(f"⚠️ **{info.get('baslik', 'Onay gerekiyor')}**\n{detay}\n\n🔐 Onaylamak için **PIN'ini** yaz.",
                      buttons=[[{"text": "❌ İptal", "callback_data": f"c:{wid}:0"}]])
        else:
            self.send(f"⚠️ **{info.get('baslik', 'Onay gerekiyor')}**\n{detay}",
                      buttons=[[{"text": "✅ Onayla", "callback_data": f"c:{wid}:1"},
                                {"text": "❌ İptal", "callback_data": f"c:{wid}:0"}]])
        ev.wait(timeout)
        if self._pin_wait and self._pin_wait.get("id") == wid:
            self._pin_wait = None
        res = self._waits.pop(wid, {"sonuc": False})["sonuc"]
        if not ev.is_set():
            self.send("⌛ 15 dakika cevap gelmedi, bu işlemi yapmadım.")
        return res

    def cancel_waits(self):
        self._pin_wait = None
        for w in list(self._waits.values()):
            w["sonuc"] = False
            w["event"].set()

    # ---------------- dinleme ----------------
    def start(self):
        if not self.token:
            return
        self._gen += 1
        gen = self._gen
        self._thread = threading.Thread(target=self._loop, args=(gen,), daemon=True)
        self._thread.start()

    def _loop(self, gen):
        try:
            me = self._call("getMe", timeout=10)
            self.username = me.get("result", {}).get("username", "")
        except Exception:
            pass
        backoff = 2
        while gen == self._gen and self.token:
            try:
                r = requests.get(API.format(token=self.token, method="getUpdates"),
                                 params={"offset": self._offset, "timeout": 50,
                                         "allowed_updates": json.dumps(["message", "callback_query"])},
                                 timeout=65).json()
                if not r.get("ok"):
                    if r.get("error_code") == 401:
                        self.error = "Bot token'ı geçersiz olmuş. Ayarlardan yeniden gir."
                        return
                    if r.get("error_code") == 409:
                        self.error = "Bu bot başka bir yerde de çalışıyor (aynı token iki programda)."
                    time.sleep(backoff)
                    continue
                self.error = ""
                backoff = 2
                for up in r.get("result", []):
                    self._offset = up["update_id"] + 1
                    try:
                        self._handle(up)
                    except Exception as e:
                        print("Telegram mesajı işlenemedi:", e)
            except Exception:
                time.sleep(backoff)  # internet yoksa bekle, sonra tekrar dene
                backoff = min(backoff * 2, 60)

    def _handle(self, up):
        if "callback_query" in up:
            cq = up["callback_query"]
            if str(cq.get("from", {}).get("id")) != str(self.chat_id) and \
               str(cq.get("message", {}).get("chat", {}).get("id")) != str(self.chat_id):
                return
            kind, wid, val = (cq.get("data", "") + "::").split(":")[:3]
            ok = val == "1"
            note = "✅ Onaylandı" if ok else "❌ İptal edildi"
            if ok and self.pin_var():  # PIN açıksa butonla onay yok, PIN istenir
                if self._kilitli():
                    note = "🔒 Telefondan onay geçici olarak kilitli"
                else:
                    self._pin_wait = {"kind": kind, "id": wid, "tries": 0}
                    note = "🔐 Onaylamak için PIN'ini yaz"
            elif kind == "c" and wid in self._waits:
                if not ok and self._pin_wait and self._pin_wait.get("id") == wid:
                    self._pin_wait = None
                self._waits[wid]["sonuc"] = ok
                self._waits[wid]["event"].set()
            elif kind == "p":
                note = self.api.bekleyen_karar(wid, ok).get("mesaj", note)
                self.api._js("refreshPending")
            try:
                self._call("answerCallbackQuery", callback_query_id=cq["id"], text=note[:190])
                self._call("editMessageReplyMarkup", chat_id=cq["message"]["chat"]["id"],
                           message_id=cq["message"]["message_id"], reply_markup={"inline_keyboard": []})
                self.send(note)
            except Exception:
                pass
            return

        msg = up.get("message") or {}
        chat = msg.get("chat", {})
        text = (msg.get("text") or "").strip()
        if not text or chat.get("type") != "private":
            return
        cid = chat.get("id")

        if not self.chat_id:  # henüz eşleşmedi
            if text.replace(" ", "") == self.pair_code:
                _save_secret(tg_chat_id=cid)
                self.send("✅ Eşleştik! Artık Robi sadece seni dinliyor.\n\n" + YARDIM,
                          chat_id=cid)
                self.api._js("tgPaired")
            else:
                self.send("👋 Robi'ye bağlanmak için bilgisayardaki **⚙️ Ayarlar → Telegram** bölümünde görünen 6 haneli kodu gönder.",
                          chat_id=cid)
            return
        if str(cid) != str(self.chat_id):
            return  # yabancı: cevap bile verme

        if self._pin_wait:
            self._handle_pin(text, msg)
            return

        low = text.lower().split("@")[0]
        if low in ("/start", "/yardim", "/help"):
            self.send(YARDIM)
        elif low == "/durum":
            self.send(self.api.durum_metni())
        elif low == "/durdur":
            if self.api._busy:
                self.api.durdur()
                self.send("⏹ Durduruyorum.")
            else:
                self.send("Şu an bir iş yapmıyorum.")
        elif low == "/onaylar":
            items = self.api.bekleyenler()
            if items:
                self.send_pending(items)
            else:
                self.send("✅ Onay bekleyen iş yok.")
        elif low == "/ekran":
            png = self.api.ekran_goruntusu()
            if png:
                self.send_photo(png, "🖥️ Ekranın şu anki hali")
            else:
                self.send("Ekran görüntüsü alınamadı.")
        else:
            self.api.telegram_mesaj(text)

    def _handle_pin(self, text, msg):
        w = self._pin_wait
        try:  # PIN sohbette görünür kalmasın
            self._call("deleteMessage", chat_id=self.chat_id, message_id=msg.get("message_id"))
        except Exception:
            pass
        low = text.lower().strip()
        if low in ("iptal", "/iptal", "vazgeç", "hayır"):
            self._pin_wait = None
            self._resolve(w, False)
            self.send("❌ İptal edildi.")
            return
        if not text.strip().isdigit():
            self.send("🔐 Önce bekleyen onayı cevapla: **PIN'ini** yaz ya da **iptal** yaz.")
            return
        if self._pin_dogru(text.strip()):
            self._pin_wait = None
            self._resolve(w, True)
            return
        w["tries"] += 1
        if w["tries"] >= 3:
            self._pin_wait = None
            self._lock_until = time.time() + 900
            self._resolve(w, False)
            self.send("🔒 3 kez yanlış PIN. İşlemi iptal ettim, telefondan onay 15 dakika kilitli.")
            self.api._js("addMessage", "sys", "⚠️ Telegram'dan 3 kez yanlış PIN girildi; telefondan onay 15 dk kilitlendi.")
        else:
            self.send(f"❌ Yanlış PIN. {3 - w['tries']} hakkın kaldı.")

    def _resolve(self, w, ok):
        if w["kind"] == "c" and w["id"] in self._waits:
            self._waits[w["id"]]["sonuc"] = ok
            self._waits[w["id"]]["event"].set()
            if ok:
                self.send("✅ PIN doğru, onaylandı.")
        elif w["kind"] == "p" and ok:
            self.send(self.api.bekleyen_karar(w["id"], True).get("mesaj", "✅ Onaylandı"))
            self.api._js("refreshPending")
