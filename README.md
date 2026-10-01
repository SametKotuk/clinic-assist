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
python -m venv .venv

# macOS/Linux: source .venv/bin/activate
.venv\Scripts\activate        
pip install -r requirements.txt

GEMINI_API_KEY=sizin_api_keyiniz
python -m uvicorn src.api.main:app --reload --port 8000