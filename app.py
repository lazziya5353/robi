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
CHATS_DIR.mkdir(exist_ok=True)

DEFAULT_CONFIG = {
    "isim": "Robi",
    "model": "qwen2.5:14b",
    "ollama_url": "http://localhost:11434",
    "kisayol": "ctrl+shift+space",
    "max_adim": 8,
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

    # --- JS -> Python ---
    def ayarlar(self):
        return {"isim": self._cfg["isim"], "model": self._cfg["model"], "kisayol": self._cfg["kisayol"]}

    def gonder(self, text):
        if self._busy:
            return False
        self._busy = True
        if not self._chat_id:
            self._chat_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        self._display.append({"r": "user", "t": text})
        threading.Thread(target=self._run, args=(text,), daemon=True).start()
        return True

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
            "hafiza": self._agent.history[1:][-30:],  # sistem mesajı hariç
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
        self._js("setStatus", text)

    def ask_confirm(self, info):
        req_id = uuid.uuid4().hex[:8]
        ev = threading.Event()
        self._pending[req_id] = {"event": ev, "sonuc": False, "baslik": info.get("baslik", "")}
        self._js("addConfirm", req_id, info)
        self.show()
        ev.wait()
        return self._pending.pop(req_id)["sonuc"]

    def _run(self, text):
        try:
            reply = self._agent.chat(text)
        except requests.ConnectionError:
            reply = ("Beynime ulaşamadım 😅 **Ollama** açık değil gibi.\n"
                     "Başlat menüsünden Ollama'yı açıp tekrar dener misin?")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                reply = (f"**{self._cfg['model']}** modeli inmemiş. "
                         f"Komut satırında `ollama pull {self._cfg['model']}` çalıştırman lazım.")
            else:
                reply = f"Bir hata oldu: {e}"
        except Exception as e:
            reply = f"Bir hata oldu: {e}"
        self._display.append({"r": "bot", "t": reply})
        self._save()
        self._busy = False
        self._js("addMessage", "bot", reply)
        self._js("refreshHistory")

    # --- pencere kontrolü ---
    def show(self):
        if self._window:
            self._window.show()
            self._window.restore()

    def hide(self):
        if self._window:
            self._window.hide()


def make_icon_image():
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((6, 10, 58, 54), radius=14, fill=(124, 92, 255))
    d.ellipse((18, 24, 28, 34), fill="white")
    d.ellipse((36, 24, 46, 34), fill="white")
    d.rounded_rectangle((22, 41, 42, 45), radius=2, fill="white")
    d.line((32, 10, 32, 3), fill=(124, 92, 255), width=3)
    d.ellipse((28, 0, 36, 7), fill=(0, 220, 180))
    return img


def main():
    cfg = load_config()
    api = Api(cfg)
    state = {"quitting": False}

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

    # --- sistem tepsisi ---
    def start_tray():
        import pystray

        def toggle(icon=None, item=None):
            api.show()

        def quit_app(icon, item):
            state["quitting"] = True
            icon.stop()
            window.destroy()

        icon = pystray.Icon(cfg["isim"], make_icon_image(), cfg["isim"], menu=pystray.Menu(
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

    # --- klavye kısayolu ---
    try:
        import keyboard
        keyboard.add_hotkey(cfg["kisayol"], api.show)
    except Exception as e:
        print("Kısayol ayarlanamadı:", e)

    webview.start(debug="--debug" in sys.argv)


if __name__ == "__main__":
    os.chdir(BASE)
    sys.path.insert(0, str(BASE))
    main()
