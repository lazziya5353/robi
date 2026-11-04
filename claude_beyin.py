"""
Claude beyni: Anthropic Messages API'ye bağlanır (ek kütüphane gerektirmez).
- Cevabı akıtarak alır, araç çağrılarını toplar.
- Her isteğin maliyetini hesaplayıp aylık harcamaya ekler; sınır aşılırsa kullanılmaz.
Anahtar gizli.json'da durur, GitHub'a hiç gitmez.
"""
import json
import time
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
SECRET = BASE / "gizli.json"
SPEND = BASE / "harcama.json"
API_URL = "https://api.anthropic.com/v1/messages"

MODELLER = {
    # model kimliği: (görünen ad, girdi $/milyon, çıktı $/milyon)  — Haiku: 100 bin parçaya kadar olan fiyat
    "claude-haiku-5-5": ("Claude Haiku 5.5", 0.10, 0.50),
    "claude-sonnet-5-5": ("Claude Sonnet 5.5", 2.00, 10.00),
}


class ClaudeHatasi(Exception):
    """Claude kullanılamadı; yerel beyne geçilebilir."""


# ---------------- anahtar ve harcama ----------------

def _secrets():
    try:
        return json.loads(SECRET.read_text(encoding="utf-8"))
    except Exception:
        return {}


def anahtar():
    return _secrets().get("anthropic_key", "").strip()


def anahtar_kaydet(key: str):
    d = _secrets()
    d["anthropic_key"] = key.strip()
    SECRET.write_text(json.dumps(d), encoding="utf-8")


def harcama():
    ay = time.strftime("%Y-%m")
    try:
        d = json.loads(SPEND.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    if d.get("ay") != ay:
        d = {"ay": ay, "usd": 0.0, "istek": 0}
    return d


def _harcama_ekle(usd: float):
    d = harcama()
    d["usd"] = round(d["usd"] + usd, 6)
    d["istek"] += 1
    SPEND.write_text(json.dumps(d), encoding="utf-8")


def kullanilabilir(cfg) -> tuple:
    """(True, '') ya da (False, sebep)"""
    if not anahtar():
        return False, "Claude anahtarı girilmemiş"
    if harcama()["usd"] >= float(cfg.get("aylik_limit_usd", 2.0)):
        return False, f"Bu ayki Claude sınırına ({cfg.get('aylik_limit_usd', 2.0)}$) ulaşıldı"
    return True, ""


# ---------------- geçmişi Claude biçimine çevir ----------------

def _tools(tools):
    return [{"name": t["function"]["name"], "description": t["function"]["description"],
             "input_schema": t["function"]["parameters"]} for t in tools]


def _messages(history):
    """Robi'nin ortak geçmişini (Ollama biçimi) Claude biçimine çevirir."""
    system, out, known_ids = "", [], set()

    def push(role, blocks):
        if out and out[-1]["role"] == role:  # art arda aynı rol → birleştir
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": list(blocks)})

    for m in history:
        role = m.get("role")
        if role == "system":
            system = m["content"]
        elif role == "user":
            push("user", [{"type": "text", "text": m.get("content") or "…"}])
        elif role == "assistant":
            blocks = []
            if (m.get("content") or "").strip():
                blocks.append({"type": "text", "text": m["content"]})
            for c in m.get("tool_calls") or []:
                cid = c.get("_id")
                if not cid:
                    continue
                args = c.get("function", {}).get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                blocks.append({"type": "tool_use", "id": cid, "name": c["function"]["name"], "input": args})
                known_ids.add(cid)
            if blocks:
                push("assistant", blocks)
        elif role == "tool":
            cid = m.get("_id")
            if cid in known_ids:
                push("user", [{"type": "tool_result", "tool_use_id": cid, "content": m.get("content", "")}])
    while out and out[0]["role"] != "user":  # ilk mesaj kullanıcıdan olmalı
        out.pop(0)
    # baştaki yetim araç sonuçlarını temizle
    if out and all(b["type"] == "tool_result" for b in out[0]["content"]):
        out.pop(0)
    return system, out


# ---------------- istek ----------------

def sor(cfg, history, tools, on_text, should_stop):
    """Claude'a sorar. Döner: Robi biçiminde assistant mesajı. Kullanılamazsa ClaudeHatasi."""
    model = cfg.get("claude_model", "claude-haiku-5-5")
    system, messages = _messages(history)
    body = {
        "model": model,
        "max_tokens": 2048,
        "system": system,
        "messages": messages,
        "thinking": {"type": "disabled"},
        "output_config": {"effort": cfg.get("claude_effort", "medium")},
        "stream": True,
    }
    if tools:
        body["tools"] = _tools(tools)
    headers = {"x-api-key": anahtar(), "anthropic-version": "2023-06-01", "content-type": "application/json"}
    try:
        r = requests.post(API_URL, headers=headers, json=body, stream=True, timeout=(10, 120))
    except requests.RequestException as e:
        raise ClaudeHatasi(f"Claude'a ulaşılamadı ({e.__class__.__name__})")
    if r.status_code != 200:
        try:
            err = r.json().get("error", {})
        except Exception:
            err = {}
        msg = err.get("message", r.text[:200])
        if r.status_code == 401:
            raise ClaudeHatasi("Claude anahtarı geçersiz. Ayarlardan yeni anahtar gir.")
        if "credit" in msg.lower() or "balance" in msg.lower():
            raise ClaudeHatasi("Claude hesabında kredi kalmamış.")
        if r.status_code in (429, 529, 500, 503):
            raise ClaudeHatasi("Claude şu an yoğun.")
        raise ClaudeHatasi(f"Claude hatası ({r.status_code}): {msg}")

    text, calls, cur = "", [], None
    usage_in, usage_out = 0, 0
    try:
        for raw in r.iter_lines(decode_unicode=True):
            if should_stop():
                break
            if not raw or not raw.startswith("data:"):
                continue
            ev = json.loads(raw[5:].strip())
            t = ev.get("type")
            if t == "message_start":
                u = ev["message"].get("usage", {})
                usage_in = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            elif t == "content_block_start":
                b = ev["content_block"]
                cur = {"type": b["type"], "id": b.get("id"), "name": b.get("name"), "json": ""}
            elif t == "content_block_delta":
                d = ev["delta"]
                if d.get("type") == "text_delta":
                    text += d["text"]
                    on_text(d["text"])
                elif d.get("type") == "input_json_delta" and cur:
                    cur["json"] += d.get("partial_json", "")
            elif t == "content_block_stop":
                if cur and cur["type"] == "tool_use":
                    try:
                        args = json.loads(cur["json"]) if cur["json"] else {}
                    except Exception:
                        args = {}
                    calls.append({"_id": cur["id"], "function": {"name": cur["name"], "arguments": args}})
                cur = None
            elif t == "message_delta":
                usage_out = ev.get("usage", {}).get("output_tokens", usage_out)
            elif t == "error":
                raise ClaudeHatasi("Claude cevap verirken hata oluştu: " + ev.get("error", {}).get("message", ""))
    finally:
        r.close()
        _, p_in, p_out = MODELLER.get(model, ("", 2.0, 10.0))
        _harcama_ekle(usage_in / 1e6 * p_in + usage_out / 1e6 * p_out)

    msg = {"role": "assistant", "content": text}
    if calls:
        msg["tool_calls"] = calls
    return msg
