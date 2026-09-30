# ClinicAssist

Diş kliniği için Türkçe yapay zeka asistanı: dokümanlardan kaynak göstererek yanıt verir, müsait saatleri sorgular, randevu oluşturur ve bilmediği konuda uydurmak yerine yönlendirir.

> Durum: Tamamlanıyor (Asama 4/6)

## Özellikle
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
pip install -e ".[dev]"

GEMINI_API_KEY=sizin_api_keyiniz
python -m uvicorn src.api.main:app --reload --port 8000

Yol haritası

- [x] Asama 1: Kapsam, mimari, örnek dokümanlar ve veri hattı (Vektör DB yerine Tool tabanlı doğrudan dosya okuma mimarisine geçiş)
- [x] Asama 2: RAG çekirdeği (XML etiketli bağlam yönetimi ve hafıza)
- [x] Asama 3: Araç kullanımı (Tool Use) ve güvenlik (Gemini 3.8-flash entegrasyonu)
- [x] Asama 4: Hata yönetimi (Graceful degradation) ve değerlendirme
- [x] Asama 5: API (FastAPI) ve kullanıcı dostu web arayüzü
- [x] Asama 6: Teslim (Güncel README, mimari diyagram ve GitHub deposu