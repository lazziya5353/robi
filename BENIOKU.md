# Robi – Bilgisayar Yardımcı Robotu 🤖

Windows'ta arka planda çalışan, yazdıklarını yapan yardımcı robot. Önemli işlerde önce sorar.

## Kurulum (bir kere)

1. **Python 3.12+** kur → https://python.org (kurarken **"Add python.exe to PATH"** kutusunu işaretle)
2. *(İsteğe bağlı — ücretsiz yerel beyin için)* **Ollama** kur → https://ollama.com
3. Bu klasördeki **`kurulum.bat`** dosyasına çift tıkla
4. **`baslat.bat`** ile Robi'yi aç. İlk açılışta masaüstüne ve Başlat menüsüne **Robi** kısayolu eklenir; sonra onu kullan.
5. *(Önerilen)* **⚙️ Ayarlar** → Claude API anahtarını gir (console.anthropic.com → API Keys). Araştırma ve zor işlerde çok daha akıllı olur.
6. *(İsteğe bağlı)* Windows açılınca başlasın: **`baslangica_ekle.bat`**

## Kullanım

- Pencereyi kapatınca kapanmaz, saatin yanındaki mor robot ikonunda arka planda çalışır. Tamamen kapatmak: ikona sağ tık → **Çıkış**
- **Ctrl + Shift + Space** → her yerden pencereyi açar
- Tek kopya çalışır; ikinci kez açarsan var olan pencere öne gelir
- Çalışırken gönder butonu **⏹** olur; basınca iş durur
- Her mesajın üstüne gelince **Kopyala** çıkar (tablolar Excel'e sütun sütun yapışır)
- Solda sohbet geçmişi; eski sohbete tıklayınca kaldığın yerden devam eder

## Beyin seçenekleri (⚙️ Ayarlar)

| Seçenek | Ne yapar | Maliyet |
|---|---|---|
| **Hep Claude** (önerilen) | Her şey Claude Haiku 5.5 ile | Mesaj başına ~$0.0005, araştırma ~$0.001 |
| **Karma** | Basit işler yerel, zor işler Claude | Daha da az |
| **Sadece yerel** | Ollama ile, internetsiz | Ücretsiz |

- **Aylık harcama sınırı** (varsayılan $2): dolunca Robi kendiliğinden yerel beyne döner.
- **Yedek arama:** Ücretsiz arama sonuç bulamazsa Claude'un resmi web araması devreye girer (arama başına $0.01). Kapatılabilir.
- Claude'a ulaşılamazsa (internet, kredi, yoğunluk) Robi takılmaz, yerel beyinle devam eder.

## Neler yapabilir?

| Direkt yapar 🟢 | Önce sorar 🟡 |
|---|---|
| İnternette araştırma, puan durumu, haber, fiyat | Dosya silme (Geri Dönüşüm Kutusu'na) |
| Word (.docx) ve Not Defteri (.txt) belgesi oluşturma | Dosya taşıma |
| YouTube'da arayıp en uygun videoyu uygulamada açma | Uygulama kaldırma |
| Program / site açma, görev çubuğundaki uygulamalar | Geçici dosyaları temizleme |
| Sistem bilgisi, klasör listeleme, dosya arama, büyük dosyalar | Zamanlı kapatma |
| Kurulu uygulamaları tarama, çok RAM yiyen programlar | |
| Ses, müzik, bilgisayarı kilitleme | |
| "Bunu hatırla" → kalıcı hafızaya yazma | |

🔴 Şifre, kart bilgisi, sistem ayarı, para işlemi, mesaj gönderme için aracı yok; yapamaz.
Windows ve Program Files gibi sistem klasörlerine dokunmaz. Web sayfalarındaki talimatlara uymaz.

## ⚡ Hızlı komutlar (anında, yapay zekâsız, ücretsiz)

- `sesi kıs` · `sesi aç` · `sesi %30 yap` · `sesi kapat`
- `durdur` / `devam et` (müzik/video) · `sonraki şarkı` · `önceki şarkı`
- `Chrome'u aç` · `Spotify aç` · `Discord'u aç` (görev çubuğu ve Başlat menüsündeki her uygulama)
- `bilgisayarı kilitle`
- `30 dakika sonra kapat` · `1 saat sonra kapat` (onay ister) · `kapatmayı iptal et`

## 🚶 Ben yokken modu

Sağ üstteki **Ben yokken** düğmesiyle ya da mesajda "ben çıkıyorum", "dönünce bakarım", "rapor et" gibi ifadelerle açılır.

- Robi soru sormadan işi sonuna kadar bitirir (40 adıma kadar)
- Riskli işleri (silme, kaldırma, kapatma) **yapmaz**, **onay listesine** koyar; dönünce tek tıkla onaylarsın
- İş sürerken bilgisayar uykuya geçmez (bilgisayarın açık olması gerekir)
- Bitince **Belgeler\Robi Raporları** klasörüne Word raporu kaydeder

## 📱 Telegram (telefondan komut ve rapor)

1. Telegram'da **@BotFather** → `/newbot` → isim ve kullanıcı adı ver → çıkan **token**'ı kopyala
2. Robi → **⚙️ Ayarlar → Telegram** → token'ı yapıştır → **Bağla**
3. Ekranda çıkan **6 haneli kodu** bota gönder → eşleşir. Bot artık sadece seni tanır.

Sonra telefondan Robi'ye normal yazar gibi iş ver. Cevap, rapor dosyası (Word) ve onay butonları telefonuna gelir.
Komutlar: `/durum` · `/durdur` · `/onaylar` · `/ekran` (ekran görüntüsü) · `/yardim`
"Ben yokken" modunda bilgisayardan verdiğin işin raporu da bitince telefonuna gelir.
Bilgisayarın açık ve uykuya geçmeyecek şekilde ayarlı olması gerekir (Ayarlar → Güç → Uyku: Hiçbir zaman).

## 🧠 Robi'nin hafızası

**⚙️ Ayarlar → Robi'nin Hafızası**: Robi bunu her mesajda okur. Tercihlerini ve kurallarını buraya yaz.
Sohbette "bunu hatırla" dersen kendisi de ekler (sadece sen istersen; web sayfaları hafızaya yazamaz).
Hafıza, anahtarlar, sohbetler ve harcama kaydı sadece bu bilgisayarda durur; GitHub'a ve güncellemelere karışmaz.

## 🔄 Güncelleme ve güvenlik ağı

- Yeni sürüm çıkınca pencerenin üstünde **"🎉 Yeni sürüm var"** yazar → **Güncelle**. Yeni kütüphane gerekiyorsa kendisi kurar.
- Bir güncelleme Robi'yi bozarsa önceki sürüme kendiliğinden döner; hata `hata.log` dosyasına yazılır.

## Sorun çıkarsa

- "Beyin kapalı" yazıyorsa ve yerel beyin kullanıyorsan → Ollama'yı Başlat menüsünden aç
- Robi açılmıyorsa → `robi` klasöründe adres çubuğuna `cmd` yaz, `python app.py --debug` çalıştır, hatayı gör
- `hata.log` dosyasını Claude'a gönderirsen sorunu bulur
