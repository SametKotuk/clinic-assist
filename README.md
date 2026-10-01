# ClinicAssist

Diş kliniği için Türkçe yapay zeka asistanı: dokümanlardan kaynak göstererek yanıt verir, müsait saatleri sorgular, randevu oluşturur ve bilmediği konuda uydurmak yerine yönlendirir.

> Durum: Tamamlandı (Asama 6/6)

## Özellikler
- **Agentic RAG:** Google Gemini SDK (`gemini-3.5-flash-lite`) ve Tool Use entegrasyonu.
- **Dinamik Belge Okuma:** `data/docs/` klasöründeki fiyat listeleri, tedavi rehberleri ve SSS belgelerini anlık tarayıp kaynak göstererek yanıt verme.
- **Araç Kullanımı (Tools):** `retrieve_docs`, `check_slots`, `book_appointment` fonksiyonları.
- **Güvenlik ve Kapsam Koruma:** Teşhis/tedavi önerisi dışı konularda yönlendirme ve prompt injection koruması.
- **Modern Arayüz:** FastAPI + temiz web sohbet arayüzü.

## Kurulum

```bash
# 1. Sanal ortam oluşturma
python -m venv .venv

# 2. Sanal ortamı aktifleştirme (Windows için)
.venv\Scripts\activate

# (macOS/Linux için ise şu komut kullanılır:)
# source .venv/bin/activate

# 3. Gerekli kütüphaneleri yükleme
pip install -r requirements.txt

# 4. .env dosyası oluşturma
# Proje ana dizininde bir .env dosyası oluşturun ve anahtarınızı ekleyin:
# GEMINI_API_KEY=sizin_api_keyiniz

# 5. Sunucuyu başlatma
python -m uvicorn src.api.main:app --reload --port 8000

##  Ekran Görüntüsü

![image alt](https://github.com/SametKotuk/clinic-assist/blob/bcd36caef0fd5aa74c466026eaa9d145008d5f1d/screenshot.jpg)
