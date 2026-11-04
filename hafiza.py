"""
Robi'nin kalıcı hafızası: hafiza.md
- Her mesajda okunur ve Robi'nin kurallarına eklenir.
- Sadece bu bilgisayarda durur, GitHub'a ve güncellemelere hiç karışmaz.
- Kullanıcı ⚙️ Ayarlar → Hafıza'dan düzenleyebilir; "bunu hatırla" deyince Robi kendisi ekler.
"""
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
FILE = BASE / "hafiza.md"
LIMIT = 8000  # karakter; hafıza her mesajda okunduğu için kısa tutulur

VARSAYILAN = """# Robi'nin hafızası
Robi bu dosyayı her mesajda okur. ⚙️ Ayarlar → Hafıza bölümünden düzenleyebilirsin.

## Kullanıcı hakkında
- Türkçe konuşur; samimi, rahat bir dil sever. "Kral" diye hitap edilebilir.
- Uzun açıklama değil, net sonuç ister. Gereksiz soru sorma, işi bitir.
- Birden fazla soruyu tek mesajda sorabilir: hepsini tek tek cevapla, hiçbirini atlama.

## Rapor tercihleri
- "Rapor et / rapor hazırla" denince: Word belgesi oluştur (word_kaydet, klasor="raporlar" → Belgeler\\Robi Raporları), sohbete de kısa bir özet yaz.
- Rapor düzeni: başta 3-5 maddelik "Özet", sonra konu başlıklarıyla detaylar, gereken yerde tablo, en sonda "Kaynaklar" (site adları).
- Rapor başlığına konu ve tarih yaz (örn. "Şampiyonlar Ligi Raporu - 04.11.2026").
- Emin olmadığın bilgileri "⚠️ Doğrulanamadı" diye işaretle; uydurma.

## Ben yokken (görev modu) kuralları
- Kullanıcı evden çıkarken iş bırakabilir ("ben çıkıyorum", "dönünce bakarım", "rapor et" gibi). Bu durumda:
  1. Görevi sonuna kadar kendin bitir. Kullanıcıya soru sorma; belirsiz bir yer varsa en makul yolu seç ve raporda "şöyle yorumladım" diye belirt.
  2. Silme, taşıma, uygulama kaldırma, bilgisayarı kapatma gibi riskli işleri YAPMA. Bunlar otomatik olarak "onay bekleyenler" listesine eklenir; kullanıcı dönünce onaylar.
  3. Mesaj gönderme, satın alma, şifre/kart bilgisi girme, sistem ayarı değiştirme ASLA yok.
  4. İş bitince mutlaka rapor hazırla: ne istendi, ne yaptın, ne buldun, nelerden emin değilsin, onay bekleyen işler neler.
  5. Bir adım başarısız olursa pes etme; başka yolu dene. Yine olmazsa raporda dürüstçe yaz.

## Hatırlanacaklar
"""


def oku() -> str:
    if not FILE.exists():
        FILE.write_text(VARSAYILAN, encoding="utf-8")
    try:
        t = FILE.read_text(encoding="utf-8")
    except Exception:
        return ""
    if len(t) > LIMIT:
        t = t[:LIMIT] + "\n…(hafıza çok uzun, gerisi okunmadı — ayarlardan kısalt)"
    return t


def yaz(text: str):
    FILE.write_text(text.replace("\r\n", "\n"), encoding="utf-8")


def ekle(bilgi: str) -> str:
    bilgi = " ".join(str(bilgi).split())[:300]
    if not bilgi:
        return "Boş bilgi eklenmedi."
    t = oku()
    if bilgi.lower() in t.lower():
        return "Bu zaten hafızamda var."
    if "## Hatırlanacaklar" not in t:
        t = t.rstrip() + "\n\n## Hatırlanacaklar\n"
    yaz(t.rstrip() + f"\n- {datetime.now():%d.%m.%Y}: {bilgi}\n")
    return "Hafızama ekledim."
