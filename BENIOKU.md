# Robi – Bilgisayar Yardımcı Robotu 🤖

Sistem tepsisinde (saatin yanında) duran, yazdıklarını yapan robot.
Tamamen ücretsiz: beyni bilgisayarında çalışan yerel bir yapay zekâ (Ollama), internet/API ücreti yok.

## Kurulum (bir kere)

1. **Python** kur → https://python.org (kurarken **"Add Python to PATH"** kutusunu işaretle)
2. **Ollama** kur → https://ollama.com (indir, kur, açık kalsın)
3. Bu klasördeki **`kurulum.bat`** dosyasına çift tıkla
   (paketleri kurar ve yapay zekâ modelini indirir, ~4.7 GB, bir kere iner)

## Kullanım

- **`baslat.bat`** → Robi açılır
- Pencereyi kapatınca kapanmaz, arka planda çalışır (saatin yanındaki mor robot ikonu)
- **Ctrl + Shift + Space** → her yerden pencereyi açar
- Tamamen kapatmak için: tepsi ikonuna sağ tık → **Çıkış**
- Windows açılınca otomatik başlasın istersen: **`baslangica_ekle.bat`**

## Neler yapabilir?

| Direkt yapar 🟢 | Önce sorar 🟡 |
|---|---|
| Sistem bilgisi (RAM, disk, işlemci) | Dosya silme (Geri Dönüşüm Kutusu'na) |
| Klasör listeleme, dosya arama | Dosya taşıma |
| En büyük dosyaları bulma | Uygulama kaldırma |
| Kurulu uygulamaları tarama | Geçici dosyaları temizleme |
| Program / web sitesi açma | |
| Çok RAM yiyen programları gösterme | |

🔴 Şifre, kart bilgisi, sistem ayarı ve para işlemleri için aracı yok, yapamaz.
Windows, Program Files gibi sistem klasörlerine de dokunmaz.

## Ayarlar (`config.json`)

- `isim`: robotun adı
- `model`: yapay zekâ modeli. Bilgisayar zayıfsa (8 GB RAM altı) `qwen2.5:3b` yap ve `ollama pull qwen2.5:3b` çalıştır.
  Güçlüyse (16 GB+ RAM / iyi ekran kartı) `qwen2.5:14b` daha akıllı olur.
- `kisayol`: pencereyi açan tuş kombinasyonu

## Sorun çıkarsa

- "Beyin kapalı" yazıyorsa → Ollama'yı başlat menüsünden aç
- Pencere açılmıyorsa → komut satırında `python app.py --debug` çalıştır, hatayı gör
