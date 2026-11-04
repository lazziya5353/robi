"""
Robi - bilgisayar yardımcı robotu
Sistem tepsisinde (saatin yanında) durur, kısayolla sohbet penceresi açılır.
"""
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

import requests
import webview

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"
CHATS_DIR = BASE / "sohbetler"
PENDING = BASE / "bekleyen_onaylar.json"
CHATS_DIR.mkdir(exist_ok=True)

DEFAULT_CONFIG = {
    "isim": "Robi",
    "model": "qwen2.5:14b",
    "ollama_url": "http://localhost:11434",
    "kisayol": "ctrl+shift+space",
    "max_adim": 8,
    "beyin": "karma",              # yerel | karma | claude
    "claude_model": "claude-haiku-5-5",
    "aylik_limit_usd": 2.0,
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    else:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


class Api:
    """Pencereden (JavaScript) çağrılan fonksiyonlar. _ ile başlayanlar dışarı açılmaz."""

    def __init__(self, cfg):
        from agent import Agent
        self._cfg = cfg
        self._window = None
        self._pending = {}
        self._busy = False
        self._agent = Agent(cfg, self)
        self._chat_id = None
        self._display = []  # ekranda görünen mesajlar: {"r": "user"|"bot"|"sys", "t": "..."}
        self._sbuf, self._stext, self._slast = "", "", 0.0
        self.away = False  # "Ben yokken" düğmesi
        self._source = "ui"    # son işi kim verdi: "ui" ya da "telegram"
        self._queue = []       # Robi meşgulken telefondan gelen işler
        self._last_task = ""
        from telegram_bag import Telegram
        self._tg = Telegram(self)

    # --- JS -> Python ---
    def ayarlar(self):
        return {"isim": self._cfg["isim"], "model": self._cfg["model"], "kisayol": self._cfg["kisayol"]}

    def gonder(self, text, kaynak="ui"):
        if self._busy:
            return False
        self._busy = True
        self._source = kaynak
        self._last_task = text
        if not self._chat_id:
            self._chat_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        self._display.append({"r": "user", "t": text})
        threading.Thread(target=self._run, args=(text,), daemon=True).start()
        return True

    # --- Telegram ---
    def telegram_mesaj(self, text):
        if self._busy:
            self._queue.append(text)
            self._tg.send(f"⏳ Şu an başka bir iş yapıyorum, bitince bunu yapacağım. (Sırada {len(self._queue)} iş var)")
            return
        self._js("remoteUser", text)
        self.gonder(text, "telegram")

    def durum_metni(self):
        import claude_beyin
        h = claude_beyin.harcama()
        s = f"⚙️ Şu an çalışıyorum: _{self._last_task[:120]}_" if self._busy else "😴 Boştayım, iş bekliyorum."
        if self._queue:
            s += f"\nSırada {len(self._queue)} iş var."
        n = len(self._pending_list())
        if n:
            s += f"\n⏳ Onay bekleyen {n} iş var → /onaylar"
        s += f"\n💰 Bu ay Claude: ${h['usd']:.3f} / ${self._cfg.get('aylik_limit_usd', 2.0)}"
        return s

    def ekran_goruntusu(self):
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab(all_screens=True)
            if img.width > 2560:
                img = img.resize((2560, int(img.height * 2560 / img.width)))
            buf = __import__("io").BytesIO()
            img.save(buf, "PNG", optimize=True)
            return buf.getvalue()
        except Exception:
            return None

    def tg_durum(self):
        return self._tg.durum()

    def tg_kaydet(self, token):
        return self._tg.kaydet(token)

    def tg_kaldir(self):
        return self._tg.kaldir()

    def tg_pin_kaydet(self, pin):
        return self._tg.pin_kaydet(pin)

    def tg_pin_kaldir(self):
        return self._tg.pin_kaldir()

    def onay(self, req_id, karar):
        item = self._pending.get(req_id)
        if item:
            item["sonuc"] = bool(karar)
            self._display.append({"r": "sys", "t": ("✓ Onaylandı: " if karar else "✕ İptal: ") + item.get("baslik", "")})
            item["event"].set()

    # --- sohbet geçmişi (bilgisayarında robi/sohbetler klasöründe saklanır) ---
    def sohbetler(self):
        out = []
        for f in CHATS_DIR.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                out.append({"id": f.stem, "baslik": d.get("baslik", "Sohbet"), "zaman": d.get("zaman", 0)})
            except Exception:
                pass
        out.sort(key=lambda x: -x["zaman"])
        return {"liste": out, "aktif": self._chat_id}

    def sohbet_ac(self, chat_id):
        if self._busy:
            return None
        f = CHATS_DIR / f"{Path(chat_id).name}.json"
        if not f.exists():
            return None
        d = json.loads(f.read_text(encoding="utf-8"))
        self._chat_id = f.stem
        self._display = d.get("ekran", [])
        self._agent.reset()
        if d.get("hafiza"):
            self._agent.history = [self._agent.history[0]] + d["hafiza"]
        return self._display

    def sohbet_sil(self, chat_id):
        f = CHATS_DIR / f"{Path(chat_id).name}.json"
        if f.exists():
            f.unlink()
        if chat_id == self._chat_id:
            self.yeni_sohbet()
        return True

    def yeni_sohbet(self):
        if self._busy:
            return False
        self._agent.reset()
        self._chat_id = None
        self._display = []
        return True

    def _save(self):
        if not self._chat_id:
            return
        first = next((m["t"] for m in self._display if m["r"] == "user"), "Sohbet")
        data = {
            "baslik": first[:48] + ("…" if len(first) > 48 else ""),
            "zaman": time.time(),
            "ekran": self._display,
            "hafiza": [{k: v for k, v in m.items() if k != "_claude_blocks"} for m in self._agent.history[1:][-30:]],
        }
        try:
            (CHATS_DIR / f"{self._chat_id}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print("Sohbet kaydedilemedi:", e)

    # --- güncelleme ---
    def guncelleme_kontrol(self):
        import updater
        return updater.kontrol((self._cfg.get("guncelleme_repo") or updater.VARSAYILAN_REPO))

    def token_kaydet(self, token):
        import updater
        updater.token_kaydet(token)
        return updater.kontrol((self._cfg.get("guncelleme_repo") or updater.VARSAYILAN_REPO))

    def guncelle(self):
        if self._busy:
            return {"durum": "hata", "mesaj": "Robi şu an meşgul, iş bitince tekrar dene."}
        import updater
        try:
            res = updater.guncelle((self._cfg.get("guncelleme_repo") or updater.VARSAYILAN_REPO))
        except Exception as e:
            return {"durum": "hata", "mesaj": f"Güncellenemedi: {e}"}
        if res.get("durum") == "tamam":
            def restart():
                time.sleep(1.5)
                updater.yeniden_baslat()
                os._exit(0)
            threading.Thread(target=restart, daemon=True).start()
        return res

    def ollama_durum(self):
        try:
            r = requests.get(self._cfg["ollama_url"].rstrip("/") + "/api/tags", timeout=3)
            models = [m["name"] for m in r.json().get("models", [])]
            return {"calisiyor": True, "model_var": any(m.startswith(self._cfg["model"]) for m in models)}
        except Exception:
            return {"calisiyor": False, "model_var": False}

    # --- Python -> JS ---
    def _js(self, fn, *args):
        if self._window:
            payload = ",".join(json.dumps(a, ensure_ascii=False) for a in args)
            self._window.evaluate_js(f"{fn}({payload})")

    def status(self, text):
        self._flush()
        self._js("setStatus", text)

    # --- akan cevap: parçaları biriktirip pencereye ~12 kez/sn gönder ---
    def stream(self, delta):
        self._sbuf += delta
        self._stext += delta
        if time.time() - self._slast > 0.08:
            self._flush()

    def _flush(self):
        if self._sbuf:
            chunk, self._sbuf = self._sbuf, ""
            self._slast = time.time()
            self._js("streamDelta", chunk)

    def stream_end(self):
        """Araç çağrısından önce yazılan ara cümleyi ayrı balon olarak bitir."""
        self._flush()
        if self._stext.strip():
            self._display.append({"r": "bot", "t": self._stext.strip()})
        self._stext = ""
        self._js("streamEnd")

    def brain(self, name, note=""):
        import claude_beyin
        label = claude_beyin.MODELLER.get(self._cfg.get("claude_model", ""), ("Claude",))[0] if name == "claude" else "Yerel beyin"
        self._js("setBrain", name, label, note)

    # --- ayarlar penceresi ---
    def ayar_getir(self):
        import claude_beyin
        h = claude_beyin.harcama()
        return {
            "beyin": self._cfg.get("beyin", "karma"),
            "claude_model": self._cfg.get("claude_model", "claude-haiku-5-5"),
            "aylik_limit_usd": self._cfg.get("aylik_limit_usd", 2.0),
            "anahtar_var": bool(claude_beyin.anahtar()),
            "claude_web_arama": self._cfg.get("claude_web_arama", True),
            "harcama_usd": h["usd"], "istek": h["istek"],
            "modeller": [{"id": k, "ad": v[0], "fiyat": f"${v[1]:g} / ${v[2]:g}"} for k, v in claude_beyin.MODELLER.items()],
        }

    def ayar_kaydet(self, d):
        import claude_beyin
        if d.get("anahtar"):
            claude_beyin.anahtar_kaydet(d["anahtar"])
        for k in ("beyin", "claude_model"):
            if d.get(k):
                self._cfg[k] = d[k]
        if "claude_web_arama" in d:
            self._cfg["claude_web_arama"] = bool(d["claude_web_arama"])
        try:
            self._cfg["aylik_limit_usd"] = max(0.0, float(d.get("aylik_limit_usd", self._cfg.get("aylik_limit_usd", 2.0))))
        except (TypeError, ValueError):
            pass
        CONFIG_PATH.write_text(json.dumps(self._cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.ayar_getir()

    def anahtar_test(self):
        """Anahtarı küçük bir istekle dener (maliyeti binde bir sent bile değil)."""
        import claude_beyin
        try:
            msg = claude_beyin.sor(self._cfg, [{"role": "user", "content": "Sadece 'tamam' yaz."}], [], lambda t: None, lambda: False)
            return {"ok": True, "mesaj": "Bağlantı çalışıyor ✅"}
        except claude_beyin.ClaudeHatasi as e:
            return {"ok": False, "mesaj": str(e)}

    def kopyala(self, text):
        """Windows panosuna yazar (tarayıcı panosu izin vermezse yedek)."""
        if not sys.platform.startswith("win"):
            return False
        import ctypes
        from ctypes import wintypes
        k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
        k32.GlobalAlloc.restype, k32.GlobalAlloc.argtypes = wintypes.HGLOBAL, [wintypes.UINT, ctypes.c_size_t]
        k32.GlobalLock.restype, k32.GlobalLock.argtypes = wintypes.LPVOID, [wintypes.HGLOBAL]
        k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        u32.OpenClipboard.argtypes = [wintypes.HWND]
        u32.SetClipboardData.restype, u32.SetClipboardData.argtypes = wintypes.HANDLE, [wintypes.UINT, wintypes.HANDLE]
        data = str(text).encode("utf-16-le") + b"\x00\x00"
        for _ in range(20):
            if u32.OpenClipboard(None):
                break
            time.sleep(0.05)
        else:
            return False
        try:
            u32.EmptyClipboard()
            h = k32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
            p = k32.GlobalLock(h)
            ctypes.memmove(p, data, len(data))
            k32.GlobalUnlock(h)
            return bool(u32.SetClipboardData(13, h))  # CF_UNICODETEXT
        finally:
            u32.CloseClipboard()

    # --- ben yokken modu ---
    def ben_yokken(self, acik):
        self.away = bool(acik)
        return self.away

    def defer(self, name, args, info):
        """Kullanıcı yokken riskli işi yapma, listeye ekle."""
        items = self._pending_list()
        items.append({"id": uuid.uuid4().hex[:8], "arac": name, "args": args, "baslik": info.get("baslik", name),
                      "detay": info.get("detay", []), "zaman": time.strftime("%d.%m %H:%M")})
        PENDING.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        self._js("refreshPending")

    def _pending_list(self):
        try:
            return json.loads(PENDING.read_text(encoding="utf-8"))
        except Exception:
            return []

    def bekleyenler(self):
        return self._pending_list()

    def bekleyen_karar(self, item_id, onay):
        items = self._pending_list()
        item = next((i for i in items if i["id"] == item_id), None)
        if not item:
            return {"mesaj": "Bu iş artık listede yok."}
        items = [i for i in items if i["id"] != item_id]
        PENDING.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        if not onay:
            return {"mesaj": "İptal edildi: " + item["baslik"]}
        from tools import run_tool
        res = run_tool(item["arac"], item["args"])
        if "hata" in res:
            return {"mesaj": "Yapılamadı: " + str(res["hata"])}
        return {"mesaj": "✓ Yapıldı: " + item["baslik"]}

    # --- hafıza (ayarlardan düzenleme) ---
    def hafiza_getir(self):
        import hafiza
        return hafiza.oku()

    def hafiza_kaydet(self, text):
        import hafiza
        hafiza.yaz(text)
        return True

    def bildir(self, text):
        """Arka planda biten işler (örn. virüs taraması) için haber: pencereye + Telegram'a."""
        self._display.append({"r": "bot", "t": text})
        self._save()
        self._js("notify", text)
        try:
            self._tg.send(text)
        except Exception:
            pass

    def durdur(self):
        self._agent.stop = True
        self._tg.cancel_waits()
        for item in list(self._pending.values()):  # bekleyen onay varsa iptal say
            item["sonuc"] = False
            item["event"].set()
        return True

    def ask_confirm(self, info):
        if self._source == "telegram" and self._tg.paired():
            return self._tg.ask(info)  # telefondaki ✅/❌ butonlarıyla
        req_id = uuid.uuid4().hex[:8]
        ev = threading.Event()
        self._pending[req_id] = {"event": ev, "sonuc": False, "baslik": info.get("baslik", "")}
        self._js("addConfirm", req_id, info)
        self.show()
        ev.wait()
        return self._pending.pop(req_id)["sonuc"]

    def _run(self, text):
        self._sbuf, self._stext = "", ""
        self._pending_before = {p["id"] for p in self._pending_list()}
        _uyanik_tut(True)  # iş sürerken bilgisayar uykuya geçmesin
        try:
            reply = self._agent.chat(text)
        except requests.ConnectionError:
            reply = ("Beynime ulaşamadım 😅 Yerel beyin (**Ollama**) çalışmıyor.\n"
                     "- Ollama kuruluysa Başlat menüsünden aç\n"
                     "- Ya da ⚙️ Ayarlar'dan **Claude anahtarı** girip beyni **Hep Claude** yap")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                reply = (f"**{self._cfg['model']}** modeli inmemiş. "
                         f"Komut satırında `ollama pull {self._cfg['model']}` çalıştırman lazım.")
            else:
                reply = f"Bir hata oldu: {e}"
        except Exception as e:
            reply = f"Bir hata oldu: {e}"
        _uyanik_tut(False)
        self._flush()
        self._display.append({"r": "bot", "t": reply})
        self._save()
        self._busy = False
        self._js("addMessage", "bot", reply)
        self._js("refreshHistory")
        self._js("refreshPending")
        self._telegram_bildir(reply)
        if self._queue:  # telefondan sıraya alınmış iş varsa devam et
            nxt = self._queue.pop(0)
            self._js("remoteUser", nxt)
            self.gonder(nxt, "telegram")

    def _telegram_bildir(self, reply):
        """Telefondan gelen işin cevabını, ya da 'ben yokken' görevinin raporunu telefona gönder."""
        if not self._tg.paired():
            return
        from_tg = self._source == "telegram"
        away_done = getattr(self._agent, "away", False)
        if not (from_tg or away_done):
            return
        try:
            self._tg.send(reply if from_tg else "📋 **Görev bitti**\n\n" + reply)
            for f in getattr(self._agent, "created_files", []):
                self._tg.send_file(f, "📄 " + Path(f).name)
            new = [p for p in self._pending_list() if p["id"] not in self._pending_before]
            if new:
                self._tg.send_pending(new)
        except Exception as e:
            print("Telegram'a gönderilemedi:", e)

    # --- pencere kontrolü ---
    def show(self):
        if self._window:
            self._window.show()
            self._window.restore()

    def hide(self):
        if self._window:
            self._window.hide()


def _uyanik_tut(acik: bool):
    """Windows'a 'çalışıyorum, uykuya geçme' der (ekran kapanabilir, bilgisayar uyumaz)."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if acik else 0))
        except Exception:
            pass


TEK_PORT = 47391  # sadece bu bilgisayarın içinden erişilen kilit kapısı


def tek_kopya_kilidi(bekle: bool):
    """Robi zaten açıksa None döner (ve açık olana 'göster' der). Değilse kilidi tutan soketi döner."""
    import socket
    for _ in range(24 if bekle else 1):  # güncelleme sonrası eski kopyanın kapanmasını bekle
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            s.bind(("127.0.0.1", TEK_PORT))
            s.listen(5)
            return s
        except OSError:
            s.close()
            time.sleep(0.5)
    try:
        c = socket.create_connection(("127.0.0.1", TEK_PORT), timeout=2)
        c.sendall(b"goster")
        c.close()
    except Exception:
        pass
    return None


def main():
    lock = tek_kopya_kilidi(bekle="--yeniden" in sys.argv)
    if lock is None:
        return  # Robi zaten açık; onun penceresini öne getirdik

    import kimlik
    kimlik.set_app_id()
    kimlik.ensure_icon()
    cfg = load_config()
    api = Api(cfg)
    import tools
    tools.BILDIR = api.bildir
    state = {"quitting": False}
    threading.Thread(target=kimlik.create_shortcuts, args=(cfg["isim"],), daemon=True).start()

    window = webview.create_window(
        cfg["isim"], str(BASE / "ui" / "index.html"), js_api=api,
        width=760, height=680, min_size=(360, 480), background_color="#0f1117",
    )
    api._window = window

    def on_closing():
        if state["quitting"]:
            return True
        window.hide()  # kapatınca kapanmasın, arka plana geçsin
        return False

    window.events.closing += on_closing

    def on_shown():
        def later():
            kimlik.apply_window_icon()
            time.sleep(3)  # açılış başarılı → güncelleme "sağlam" sayılır
            (BASE / "yeni_guncelleme").unlink(missing_ok=True)
        threading.Thread(target=later, daemon=True).start()  # pencereyi bekletme

    window.events.shown += on_shown

    # ikinci kez açılmaya çalışılırsa pencereyi öne getir
    def lock_listener():
        while True:
            try:
                conn, _ = lock.accept()
                if conn.recv(16) == b"goster":
                    api.show()
                conn.close()
            except Exception:
                time.sleep(1)

    threading.Thread(target=lock_listener, daemon=True).start()
    api._tg.start()  # Telegram bağlıysa telefonu dinlemeye başla

    # --- sistem tepsisi ---
    def start_tray():
        import pystray

        def toggle(icon=None, item=None):
            api.show()

        def quit_app(icon, item):
            state["quitting"] = True
            icon.stop()
            window.destroy()

        icon = pystray.Icon(cfg["isim"], kimlik.make_icon_image(64), cfg["isim"], menu=pystray.Menu(
            pystray.MenuItem("Aç", toggle, default=True),
            pystray.MenuItem("Çıkış", quit_app),
        ))
        icon.run()

    threading.Thread(target=start_tray, daemon=True).start()

    # --- beyni önceden ekran kartına yükle (ilk mesaj beklemesin) ---
    def warmup():
        try:
            requests.post(cfg["ollama_url"].rstrip("/") + "/api/generate",
                          json={"model": cfg["model"], "prompt": "", "keep_alive": cfg.get("hafizada_tut", "60m")},
                          timeout=300)
        except Exception:
            pass

    threading.Thread(target=warmup, daemon=True).start()

    # --- klavye kısayolu (Windows'un kendi sistemiyle) ---
    import kisayol
    if not kisayol.baslat(cfg["kisayol"], api.show):
        print("Kısayol ayarlanamadı (başka bir program aynı tuşları kullanıyor olabilir):", cfg["kisayol"])

    webview.start(debug="--debug" in sys.argv)


if __name__ == "__main__":
    os.chdir(BASE)
    sys.path.insert(0, str(BASE))
    main()
