# Demo — 4 Kasım 2026

## Hazırlık (demodan 15 dk önce)

```bash
cd ~/Desktop/erp-asistan
docker compose up -d
scripts/reset_demo.sh            # temiz veri, ~1 dk
lms ps; ollama ps                # LM Studio'da model yüklü olmasın (16 GB RAM)
uv run erp-asistan               # http://localhost:7860
```

- Odoo: http://localhost:8069/odoo?db=erp → `admin` / `admin`
- İki pencere yan yana: solda asistan, sağda Odoo.
- Isınma: "Stokta 5'ten az kalan ürünler hangileri?" (ilk cevap modeli belleğe yükler).
- Mikrofon izni: tarayıcı ilk kayıtta sorar, önceden ver.
- `samples/invoices/fatura-ege-bilisim.png` dosyasını yazdır (kamera anı için).
- Sonra Wi-Fi'yi kapat.

## Akış (~10 dk)

1. **Sorgu**: "Anadolu Gıda'nın açık faturaları toplam ne kadar?" → araç izini aç ve göster.
2. **Analiz**: "Ekim ve Kasım satışlarını karşılaştır."
3. **Tekil yazma + onay**: "Yeni müşteri ekle: Boğaziçi Danışmanlık, İstanbul" → onay kutusu → Onayla → Odoo'da Kişiler'de göster.
4. **Çok adımlı (sesli)**: 🎤 "Kaya Tekstil'e 2 adet ergonomik ofis sandalyesi için teklif oluştur, onayla ve faturasını kes" → 3 onay → Odoo'da fatura.
5. **Reddetme**: "Lazer yazıcının fiyatını 7.900 TL yap" → Reddet → hiçbir şey değişmedi.
6. **Fotoğraftan fatura**: 📷 sekmesi → kamera ile basılı faturayı çek → Oku → tabloyu göster → bir satırı sil → ⚠️ uyarı + işlem engeli → geri ekle → İşle → Odoo'da aç.
7. **Kapanış**: Wi-Fi kapalı. Hepsi bu bilgisayarda, veri dışarı çıkmadı.

## Akılda kalacak mesajlar

- Model ERP'ye doğrudan erişmiyor. 12 dar kapsamlı araç kullanıyor. Her yazma işlemi insan onayından geçiyor.
- Hesap yapmıyor. Toplamları ERP hesaplıyor. Model bir testte açık faturaları 100.000 TL yanlış toplamıştı.
- Kendi hatasını gizleyemiyor. Araç çağırmadan "oluşturuldu" derse sistem bunu yakalıyor (🛡️ denetim).
- Fatura okumada çapraz kontrol var: kalemler toplamı tutmazsa fatura işlenmiyor.
- Ölçüm: `reports/` altındaki eval raporu. 16 senaryo × 5 koşu.

## Olası sorular

- **Canlıya nasıl geçer?** Daha güçlü bir makine ve daha büyük bir model gerekiyor (ör. 27B–70B). Araç katmanı MCP server olarak paketlenir. Kullanıcı bazlı Odoo API key'leri kullanılır, tüm işlemler audit log'a yazılır.
- **Yanlış müşteriye işlem yaparsa?** Ad belirsizse araç birden fazla adayı döndürür ve model kullanıcıya sorar. Onay kutusu son kontrol noktası.
- **Neden bulut modeli değil?** KVKK ve ticari sırlar. Ayrıca internet bağlantısı gerekmiyor.
