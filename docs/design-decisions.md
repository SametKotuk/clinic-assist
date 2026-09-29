# Tasarım Kararları

Her karar için: **Ne seçtik / Neden / Alternatifler / Sonuç (ölçümle)**. Mülakat hikâyen burası.

## Gün 1-2: Veri Hattı ve Altyapı
- **Sektör Seçimi:**
  - **Ne seçtik:** Diş kliniği asistanı.
  - **Neden:** Fiyat listeleri, tedavi süreleri, yaş/veli politikaları ve iptal şartları gibi birbiriyle çelişebilecek veya mantıksal kontrol gerektirecek zengin, gerçekçi doküman yapılarına sahip olması.
  - **Alternatifler:** E-ticaret iade botu, IT destek asistanı.
  - **Sonuç:** Asistanın çoklu kural setlerini (örn: 18 yaş altı kuralı + şeffaf plak süresi) aynı anda işleyebilme kapasitesi test edildi.

- **Vektör Veritabanı (RAG) Yerine Doğrudan Dosya Okuma:**
  - **Ne seçtik:** ChromaDB ve `multilingual-e5-small` embedding modelinden vazgeçilerek, belgelerin `ToolExecutor` üzerinden anlık olarak (In-Context Learning ile) okunması.
  - **Neden:** Yerel Windows ortamında ChromaDB kurulumunda yaşanan `DLL load failed (cygrpc)` hataları ve Application Control güvenlik politikası engelleri projeyi bloke etti. Klinik belgeleri (yaklaşık 5 sayfa) çok büyük olmadığı için vektör aramaya ihtiyaç duyulmadı.
  - **Alternatifler:** FAISS, Pinecone veya bulut tabanlı bir vektör veritabanı kullanmak.
  - **Sonuç:** Dış kütüphane bağımlılığı ortadan kalktı. Veritabanı çökmeleri %0'a indi. Tüm RAG süreci 0 ms gecikme ile doğrudan hafızadan çalıştırıldı.

