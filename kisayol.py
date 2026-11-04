"""
Genel kısayol tuşu (örn. Ctrl+Shift+Space) — Windows'un kendi RegisterHotKey sistemiyle.
Klavyeyi dinleyen kütüphane kullanmaz; sadece bu tuş kombinasyonu basılınca Windows haber verir.
"""
import sys
import threading

MODS = {"ctrl": 0x2, "control": 0x2, "shift": 0x4, "alt": 0x1, "win": 0x8}
KEYS = {"space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "backspace": 0x08}
KEYS.update({f"f{i}": 0x6F + i for i in range(1, 13)})


def _parse(combo: str):
    mods, vk = 0x4000, None  # MOD_NOREPEAT: basılı tutunca tekrar tetiklenmesin
    for part in combo.lower().replace(" ", "").split("+"):
        if part in MODS:
            mods |= MODS[part]
        elif part in KEYS:
            vk = KEYS[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
    return mods, vk


def baslat(combo: str, callback) -> bool:
    if not sys.platform.startswith("win"):
        return False
    mods, vk = _parse(combo)
    if vk is None:
        return False
    ready, result = threading.Event(), {"ok": False}

    def loop():
        import ctypes
        from ctypes import wintypes
        u32 = ctypes.windll.user32
        result["ok"] = bool(u32.RegisterHotKey(None, 1, mods, vk))
        ready.set()
        if not result["ok"]:
            return
        msg = wintypes.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312:  # WM_HOTKEY
                try:
                    callback()
                except Exception:
                    pass

    threading.Thread(target=loop, daemon=True).start()
    ready.wait(3)
    return result["ok"]
