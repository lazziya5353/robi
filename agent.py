"""
Robi'nin beyni: kullanıcının yazdığını yerel modele (Ollama) verir,
model hangi aracı çağırmak istiyorsa onu çalıştırır, sonucu geri verir.
Onaylı araçlarda önce arayüzden kullanıcıya sorar.
"""
import json
import requests

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
- Güncel bilgi istenince (puan durumu, fikstür, maç sonucu, haber, fiyat, hava vb.):
  1) web_ara ile ara. 2) Sonuçlardan en güvenilir olanı sayfa_oku ile oku (istediğin bölüm için 'odak' kullan, örn odak="Puan durumu").
  3) Aradığın yoksa ya da sayfa okunamadıysa SIRADAKİ sonuca geç, en fazla 4 sayfa dene.
  4) Bulduğun bilgiyi sohbete YAZ (tablo gerekiyorsa markdown tablo: | Sıra | Takım | P |), sonuna kaynağın adresini ekle.
  Bilgiyi kendi aklından uydurma, sadece okuduğun sayfadan yaz. Sayfayı tarayıcıda açmak (web_ac) sadece kullanıcı "aç" derse.
  Adres uydurma: sadece web_ara'dan gelen adresleri kullan. Bugünün tarihi: {tarih}.
- "Araştır ve not defterine/dosyaya kaydet" denirse: ÖNCE yukarıdaki gibi araştır ve bilgiyi topla, SONRA not_kaydet ile topladığın bilginin tamamını (başlık, tarih, bilgi, kaynak) kaydet. Boş not ya da sadece Not Defteri'ni açmak YASAK; uygulama_ac ile notepad açma.
- YouTube isteği gelince: önce youtube_ara ile ara, sonuçlardan kullanıcının istediğine en uygununu seç (başlık, süre, izlenme, kanal), 1 cümleyle neden seçtiğini söyle ve youtube_ac(video_id=...) ile aç. Kullanıcı sadece "YouTube'u aç" derse youtube_ac'ı parametresiz çağır.
- Cevaplarında uzun listeleri madde madde ve kısa tut.
"""


class Agent:
    def __init__(self, config, ui):
        self.cfg = config
        self.ui = ui
        self.reset()

    def reset(self):
        from datetime import date
        self.history = [{"role": "system", "content": SYSTEM.format(
            isim=self.cfg.get("isim", "Robi"), tarih=date.today().strftime("%d.%m.%Y"))}]

    def _ask_model(self):
        url = self.cfg.get("ollama_url", "http://localhost:11434").rstrip("/") + "/api/chat"
        r = requests.post(url, json={
            "model": self.cfg.get("model", "qwen2.5:7b"),
            "messages": self.history,
            "tools": TOOLS,
            "stream": False,
            "keep_alive": self.cfg.get("hafizada_tut", "60m"),
            "options": {"temperature": 0.2, "num_ctx": int(self.cfg.get("hafiza_boyutu", 8192))},
        }, timeout=600)
        r.raise_for_status()
        return r.json()["message"]

    def _shrink(self):
        """Hafıza dolmasın: en son 2 araç sonucu hariç eski araç sonuçlarını kısalt."""
        tool_idx = [i for i, m in enumerate(self.history) if m.get("role") == "tool"]
        for i in tool_idx[:-2]:
            c = self.history[i]["content"]
            if len(c) > 600:
                self.history[i]["content"] = c[:600] + " ...(eski sonuç, kısaltıldı)"

    def chat(self, text: str) -> str:
        self.history.append({"role": "user", "content": text})
        # Çok uzun sohbetlerde hafızayı kırp (sistem mesajı kalsın)
        if len(self.history) > 40:
            self.history = [self.history[0]] + self.history[-30:]

        for _ in range(max(int(self.cfg.get("max_adim", 8)), 14)):
            self._shrink()
            self.ui.status("Düşünüyorum")
            msg = self._ask_model()
            self.history.append(msg)
            calls = msg.get("tool_calls") or []
            if not calls:
                return msg.get("content", "").strip() or "Tamamdır."

            for call in calls:
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
                self.history.append({"role": "tool", "content": content, "tool_name": name})

        return "Bu iş çok fazla adım sürdü kral, biraz daha parçalara bölebilir misin?"
