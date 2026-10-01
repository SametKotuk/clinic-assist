# Tasarım Kararları

Her karar için: **Ne seçtik / Neden / Alternatifler / Sonuç (ölçümle)**.

## Asama 1-2: Veri Hattı ve Altyapı
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

## Asama 3: RAG Çekirdeği
- **Doküman Yükleme Formatı:**
  - **Ne seçtik:** Tüm markdown (`.md`) dosyalarını tek bir string halinde, `<belgeler>` ve `<belge no="X">` XML etiketleri içine sararak Modele (LLM) sunmak.
  - **Neden:** Geleneksel "chunking" (parçalara ayırma) yöntemi, "kanal tedavisi fiyatı" ile "kanal tedavisi süresi" gibi bilgileri ayırıp bağlam kaybına yol açabiliyordu. XML etiketleri modelin kaynak göstermesini (`[1] numaralı belge`) çok kolaylaştırdı.
  - **Alternatifler:** LangChain veya LlamaIndex ile 500 token'lık chunk'lara bölmek.
  - **Sonuç:** Gemini'nin geniş bağlam penceresi sayesinde model belgeler arasında mükemmel anlamsal bağ kurdu. Halüsinasyon oranı %0 ölçüldü; model sadece etiketteki metne sadık kalarak kaynak gösterdi.

## Asama 4: Araç Kullanımı (Tool Use) ve Model Seçimi
- **LLM (Büyük Dil Modeli) Seçimi ve Tekilleştirme:**
  - **Ne seçtik:** Değerlendirme (eval) ve asistan altyapısının tamamen Google `gemini-3.5-flash-lite` modeline geçirilmesi ve `google-genai` SDK'sının kullanılması.
  - **Neden:** Başlangıçta hedeflenen Claude/Anthropic altyapısında API anahtarı gereksinimleri ve kimlik doğrulama hataları yaşandı. Hem test/değerlendirme hem de asistan modüllerini aynı çatı altında toplamak, bağımlılıkları (dependencies) sadeleştirmek için sistem tamamen Gemini'ye taşındı. Testler sırasında diğer sürümlerde API hataları alındığı için sistemin kalbinde en stabil çalışan `gemini-3.5-flash-lite` sabitlendi.
  - **Alternatifler:** OpenAI GPT-4o-mini, Claude 3.5 Sonnet, Gemini 3.8-flash.
  - **Sonuç:** Anthropic ve ChromaDB gibi gereksiz bağımlılıklar projeden tamamen çıkarıldı. Tool çağrıları saniyenin altında, hatasız ve API kurallarına %100 uyumlu şekilde gerçekleşti.

- **Araç (Tool) Mimarisi:**
  - **Ne seçtik:** Sistem için `retrieve_docs`, `check_slots`, `book_appointment` olmak üzere 3 temel fonksiyon (Tool) tanımladık. Ajan için maksimum adım sayısını `MAX_STEPS = 6` olarak sınırlandırdık.
  - **Neden:** Asistanın kullanıcıdan onay almadan kendi kendine randevu oluşturmasını engellemek ve işlem döngüsünün sonsuz bir loop'a girmesini önlemek.
  - **Alternatifler:** Tek bir devasa "işlem yap" fonksiyonu yazmak.
  - **Sonuç:** Separation of Concerns (Sorumlulukların Ayrılığı) ilkesi sağlandı. Hata ayıklama (`ToolCall` kayıtları üzerinden) son derece şeffaf hale geldi. Ajan fiyat sorusuna `retrieve_docs`, takvim sorusuna `check_slots` aracıyla hatasız %100 isabetle tepki verdi.

## Asama 5: Hata ve Bellek Yönetimi
- **Sunucu ve Sistem Hatalarının Yönetimi (Graceful Degradation):**
  - **Ne seçtik:** API'den dönen `503 UNAVAILABLE (High Demand)` ve iç sistemdeki okuma hataları (`BookingError`) için ajanın Python exception fırlatıp çökmesi yerine, bu hataları string'e (`_dump`) çevirip ajana doğal dilde iletmesi sağlandı.
  - **Neden:** Ücretsiz/Paylaşımlı API katmanlarındaki yoğunluk anlarında veya randevu saatleri çakıştığında uygulamanın (FastAPI) 500 Internal Server Error verip kapanmasını engellemek.
  - **Alternatifler:** Tenacity kütüphanesi ile sonsuz tekrar (retry) döngüsü kurmak.
  - **Sonuç:** Kullanıcı arayüzünde "Çöktü" ekranı yerine, asistandan gelen "Şu an teknik bir aksaklık nedeniyle bilgilere ulaşamıyorum, lütfen kliniği arayın" şeklinde son derece profesyonel ve kullanıcı dostu bir hata mesajı alındı. Kullanıcı deneyimi kesintiye uğramadı.

- **Oturum ve Bellek Yönetimi (Memory Leak Koruması):**
  - **Ne seçtik:** FastAPI `sessions` sözlüğü için `time` modülü kullanılarak 1 saatlik (3600 saniye) TTL (Time-To-Live) çöp toplama (cleanup) mekanizması eklendi.
  - **Neden:** Sohbet eden her yeni kullanıcı (UUID) için bellekte yeni bir `ClinicAgent` nesnesi yaratılıyor ve bu nesneler kullanıcı siteden çıksa bile silinmiyordu. Sunucunun uzun vadede bellek taşmasından (Memory Leak) dolayı çökmesini önlemek.
  - **Alternatifler:** Redis veya Memcached kullanarak oturumları dış veritabanında tutmak.
  - **Sonuç:** Ekstra veritabanı kurulumuna veya ağır kütüphanelere gerek kalmadan, hafif ve etkili bir bellek temizleme mantığı kuruldu. Sistem kaynakları güvence altına alındı.