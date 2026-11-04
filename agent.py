"""
Robi'nin beyni: kullanıcının yazdığını yerel modele (Ollama) verir,
model hangi aracı çağırmak istiyorsa onu çalıştırır, sonucu geri verir.
Onaylı araçlarda önce arayüzden kullanıcıya sorar.
"""
import json
import re
import uuid

import requests

import claude_beyin

from tools import TOOLS, ONAYLI, run_tool, describe_action, status_text

SYSTEM = """Sen {isim}, kullanıcının Windows bilgisayarında çalışan yardımcı robotsun.
Türkçe, samimi ve kısa konuş. Kullanıcıya "kral" diye hitap edebilirsin.

Kurallar:
- Kullanıcının istediğini araçlarla yap. Tahmin yürütme; bilmediğin şeyi araçla kontrol et.
- Silme, taşıma, uygulama kaldırma ve geçici dosya temizleme araçlarını çağırınca sistem kullanıcıdan otomatik onay ister. Sen ayrıca "onaylıyor musun" diye sorma, direkt aracı çağır.
- "Gereksiz uygulama" sorulduğunda önce listele, sonra hangilerinin neden gereksiz olabileceğini kısaca açıkla, kendi kendine silme. Kullanıcı seçsin.
- Şifre, kart bilgisi, sistem/güvenlik ayarı, para işlemi ASLA yapma; bunlar için aracın yok.
- DÜRÜSTLÜK EN ÖNEMLİ KURAL: Sadece araç sonucunda yazanı söyle. Araç "TARAYICIDA açıldı" diyorsa "uygulamada açtım" deme. Araç çağırmadan "açtım/yaptım" asla deme. Hata geldiyse hatayı aynen söyle.
- Yapamadığın bir şey istenirse dürüstçe "bunu henüz yapamıyorum" de.
- Güncel bilgi istenince (puan durumu, fikstür, maç sonucu, haber, fiyat, hava, kur vb.):
  1) ÖNCE arastir aracını çağır (ücretsiz; soru=kullanıcının sorusu, arama=kısa ve net arama sorgusu, gerekirse sezon/yıl ekle).
     arastir boş, hatalı ya da alakasız sonuç getirirse ve web_search aracın varsa web_search'ü kullan (ücretli, gerekmedikçe kullanma).
  2) Gelen içeriklerden cevabı KENDİN yaz: doğrudan bilgiyi ver, puan durumu/fikstür gibi şeyleri markdown tablo yap (| Sıra | Takım | O | P |).
  3) ASLA link ya da adres yazma, "şu siteden bakabilirsin" deme. En sona tek satır: "Kaynak: beIN SPORTS, Vikipedi" gibi sadece site adları.
  4) Yine cevap yoksa dürüstçe "bulamadım" de. Bilgi uydurma.
  Sayfayı tarayıcıda açmak (web_ac) sadece kullanıcı "aç" derse. Bugünün tarihi: {tarih}.
- Cevapların kısa ve öz olsun; gereksiz giriş/kapanış cümlesi yazma.
- "Araştır ve not defterine/dosyaya kaydet" denirse: ÖNCE yukarıdaki gibi araştır ve bilgiyi topla, SONRA not_kaydet ile topladığın bilginin tamamını (başlık, tarih, bilgi, kaynak) kaydet. Boş not ya da sadece Not Defteri'ni açmak YASAK; uygulama_ac ile notepad açma.
- YouTube isteği gelince: önce youtube_ara ile ara, sonuçlardan kullanıcının istediğine en uygununu seç (başlık, süre, izlenme, kanal), 1 cümleyle neden seçtiğini söyle ve youtube_ac(video_id=...) ile aç. Kullanıcı sadece "YouTube'u aç" derse youtube_ac'ı parametresiz çağır.
- Cevaplarında uzun listeleri madde madde ve kısa tut.
"""


class Agent:
    def __init__(self, config, ui):
        self.cfg = config
        self.ui = ui
        self.stop = False
        self.brain, self._brain_note = "yerel", ""
        self.reset()

    def reset(self):
        from datetime import date
        self.history = [{"role": "system", "content": SYSTEM.format(
            isim=self.cfg.get("isim", "Robi"), tarih=date.today().strftime("%d.%m.%Y"))}]

    # ---------------- hangi beyin? ----------------
    _ZOR = re.compile(r"araştır|nedir|kimdir|nasıl|neden|niye|hangi|kaç|puan|fikstür|maç|skor|haber|fiyat|kur|dolar|"
                      r"euro|hava durumu|karşılaştır|özetle|öner|tavsiye|plan|anlat|açıkla|çevir|yorumla|youtube|"
                      r"tablo|yaz|hesapla|\?")

    def _choose_brain(self, text: str) -> str:
        mode = self.cfg.get("beyin", "karma")
        if mode == "yerel":
            return "yerel"
        ok, why = claude_beyin.kullanilabilir(self.cfg)
        if not ok:
            self._brain_note = why
            return "yerel"
        if mode == "claude":
            return "claude"
        # karma: kısa ve basit bilgisayar işleri yerelde, gerisi Claude'da
        t = text.lower()
        return "claude" if len(t) > 70 or self._ZOR.search(t) else "yerel"

    def _ask_model(self):
        if self.brain == "claude":
            try:
                return claude_beyin.sor(self.cfg, self.history, TOOLS, self.ui.stream, lambda: self.stop, self.ui.status)
            except claude_beyin.ClaudeHatasi as e:
                self.brain = "yerel"  # bu iş yerel beyinle devam etsin
                self._brain_note = str(e)
                self.ui.brain("yerel", str(e))
        return self._ask_local()

    def _ask_local(self):
        """Yerel modele sorar; cevap yazıldıkça arayüze akıtır. Araç çağrılarını da toplar."""
        url = self.cfg.get("ollama_url", "http://localhost:11434").rstrip("/") + "/api/chat"
        r = requests.post(url, json={
            "model": self.cfg.get("model", "qwen2.5:7b"),
            "messages": [{k: v for k, v in m.items() if not k.startswith("_")} for m in self.history],
            "tools": TOOLS,
            "stream": True,
            "keep_alive": self.cfg.get("hafizada_tut", "60m"),
            "options": {"temperature": 0.2, "num_ctx": int(self.cfg.get("hafiza_boyutu", 8192))},
        }, timeout=600, stream=True)
        r.raise_for_status()
        content, tool_calls = "", []
        try:
            for line in r.iter_lines():
                if self.stop:
                    raise Durduruldu()
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("error"):
                    raise RuntimeError(chunk["error"])
                m = chunk.get("message") or {}
                if m.get("content"):
                    content += m["content"]
                    self.ui.stream(m["content"])
                if m.get("tool_calls"):
                    tool_calls += m["tool_calls"]
                if chunk.get("done"):
                    break
        finally:
            r.close()
        msg = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        return msg

    def _shrink(self):
        """Hafıza dolmasın: en son 2 araç sonucu hariç eski araç sonuçlarını kısalt."""
        tool_idx = [i for i, m in enumerate(self.history) if m.get("role") == "tool"]
        for i in tool_idx[:-2]:
            c = self.history[i]["content"]
            if len(c) > 600:
                self.history[i]["content"] = c[:600] + " ...(eski sonuç, kısaltıldı)"

    def chat(self, text: str) -> str:
        self.stop = False
        self.history.append({"role": "user", "content": text})
        # Çok uzun sohbetlerde hafızayı kırp (sistem mesajı kalsın)
        if len(self.history) > 40:
            self.history = [self.history[0]] + self.history[-30:]

        # Basit komutlar yapay zekâya gitmeden anında yapılır
        import hizli
        quick = hizli.eslestir(text)
        if quick:
            reply = self._run_quick(quick)
            self.history.append({"role": "assistant", "content": reply})
            return reply

        for m in self.history:  # önceki turların ham Claude bloklarına artık gerek yok (hafıza şişmesin)
            m.pop("_claude_blocks", None)
        self._brain_note = ""
        self.brain = self._choose_brain(text)
        self.ui.brain(self.brain, self._brain_note)
        try:
            return self._loop()
        except Durduruldu:
            self.history.append({"role": "assistant", "content": "(Kullanıcı işi durdurdu.)"})
            return "⏹ Durdurdum kral."

    def _run_quick(self, q):
        if q.get("onay"):
            if not self.ui.ask_confirm(q["onay"]):
                return "Tamam, iptal ettim."
        try:
            return q["yap"]()
        except Exception as e:
            return f"Yapamadım: {e}"

    def _loop(self) -> str:
        for _ in range(max(int(self.cfg.get("max_adim", 8)), 14)):
            if self.stop:
                raise Durduruldu()
            self._shrink()
            self.ui.status("Düşünüyorum")
            msg = self._ask_model()
            self.history.append(msg)
            calls = msg.get("tool_calls") or []
            if not calls:
                return msg.get("content", "").strip() or "Tamamdır."
            self.ui.stream_end()  # araçtan önce yazdığı ara cümle ayrı balonda kalsın

            for call in calls:
                if self.stop:
                    raise Durduruldu()
                call.setdefault("_id", "t" + uuid.uuid4().hex[:12])
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                if name in ONAYLI:
                    ok = self.ui.ask_confirm(describe_action(name, args))
                    if self.stop:
                        raise Durduruldu()
                    if ok:
                        self.ui.status("Yapıyorum")
                        result = run_tool(name, args)
                    else:
                        result = {"iptal": "Kullanıcı bu işlemi onaylamadı. Yapma ve başka öneri sunma, sadece tamam de."}
                else:
                    self.ui.status(status_text(name))
                    result = run_tool(name, args)

                content = json.dumps(result, ensure_ascii=False)
                if len(content) > 8000:  # küçük modeller için kırp
                    content = content[:8000] + " ...(kırpıldı)"
                self.history.append({"role": "tool", "content": content, "tool_name": name, "_id": call["_id"]})

        return "Bu iş çok fazla adım sürdü kral, biraz daha parçalara bölebilir misin?"


class Durduruldu(Exception):
    pass
