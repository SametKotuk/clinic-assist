import traceback

print("1. Asistan başlatılıyor...")
try:
    from src.agent.agent import ClinicAgent
    agent = ClinicAgent()
    
    print("2. Soru soruluyor...")
    cevap = agent.chat("Diş taşı temizliği ne kadar?")
    
    print("3. İŞLEM BAŞARILI. Cevap:")
    print(cevap.text)
    
    print("\n--- ARKA PLAN İŞLEMLERİ (GİZLİ HATALAR) ---")
    for c in cevap.tool_calls:
        print(f"Araç: {c.name} | Hata: {c.is_error} | Sonuç: {c.result}")
        
except Exception as e:
    print("\n🚨 İŞTE GİZLENEN HATA BURADA:\n")
    traceback.print_exc()