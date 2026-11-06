# Demo runbook

## Hazırlık (demodan 15 dk önce)

Sıfırlama sırası; her biri bir öncekinin bitmesini bekler:

```bash
cd ~/Desktop/erp-asistan
pkill -f erp-asistan; while pgrep -qf erp-asistan; do sleep 1; done   # asistan kapanmadan sıfırlama yapma
docker compose up -d                                  # Odoo
docker compose -f docker/erpnext/compose.yml up -d    # ERPNext (Docker Desktop'tan da başlatılabilir)
scripts/reset_demo.sh            # Odoo: temiz veri (SEED_DATASET), ~1 dk; sohbet geçmişini siler, ODOO_API_KEY yenilenir
scripts/reset_erpnext.sh         # ERPNext: temiz veri, ~1 dk; ERPNEXT_API_KEY yenilenir
pgrep -qf "LM Studio" && lms ps; ollama ps   # model yüklü olmasın (16 GB RAM); lms ps kapalı LM Studio'yu başlatır
nohup uv run erp-asistan > /tmp/erp-asistan.log 2>&1 &   # http://localhost:7860 (anahtarlar değiştiği için yeniden başlatma şart)
```

Temiz veride iki ERP'nin özet kartları birebir aynı olmalı; beklenen sayılar veri setinin `private/<veri-seti>/DEMO.md` dosyasında.

- Odoo: http://localhost:8069/odoo?db=erp → `admin` / `admin`
- ERPNext: http://localhost:8080 → `Administrator` / `admin`
- İki pencere yan yana: solda asistan, sağda Odoo. Asistan yarım ekranda tek sütun çalışır.
- Başlıktaki iki ışık (Yapay Zeka, ERP) yeşil yanıp sönmeli; ERP'nin sağındaki seçici aktif ERP'yi gösterir.
- Isınma: ilk komut modeli belleğe yükler (~15 sn). Demodan önce bir sorgu çalıştırın, Yeni sohbet'e basın, sonra `rm history/*.json` (ısınma geçmişte görünmesin).
- Mikrofon ve kamera izinlerini tarayıcı ilk kullanımda sorar; önceden verin.
- Bellek: Docker Desktop 3 GB ile sınırlı; iki ERP birlikte ~1,3 GB (6 Kas ölçümü). `memory_pressure` %20'nin altındaysa gereksiz uygulamaları kapatın.

## Arayüz

- **Konuş**: basın, konuşun, tekrar basın. Ya da metin kutusu dışında Boşluk tuşunu basılı tutun. Esc iptal eder.
- Her araç çağrısı bir LED satırı: yeşil tamamlandı, amber onay bekliyor, kırmızı vazgeçildi veya denetim uyarısı. Satıra tıklayınca parametre ve sonuç görünür.
- Boş ekranda tanıtım, ERP özeti ve örnek komutlar. Tıklanan komut yazma alanına gelir; Gönder ile çalışır.
- Sol panel: Yeni sohbet, Fatura oku, geçmiş sohbetler (salt okunur) ve Yardım. ☰ ile kapanır; dar ekranda çekmece olur.
- **Fatura oku**: görseli bırakın, yapıştırın veya kamerayla çekin. Toplamlar ya da tarih tutmazsa "ERP'ye işle" kilitli kalır.
- **ERP seçici** (sağ üst): Odoo / ERPNext. Seçim yeni sohbet açar; eski sohbet geçmişte ERP adıyla kalır. Kapalı ERP "· kapalı" görünür, seçilemez; açılınca ~10 sn içinde seçilebilir olur. Aynı anda tek canlı sohbet: iki sekmede iki ERP kullanmayın.

## Akılda kalacak mesajlar

- Model ERP'ye doğrudan erişmiyor; 13 dar kapsamlı araç kullanıyor. Her yazma işlemi insan onayından geçiyor.
- Hesap yapmıyor: toplamlar, dönem farkları ve tarih dönüşümleri kodda. Model bu işlerde ölçülebilir hata yapıyordu.
- Kendi hatasını gizleyemiyor: araç çağırmadan "oluşturuldu" derse denetim yakalıyor.
- Fatura okumada çapraz kontrol var; ama her okuma hatasını yakalamaz. Son kontrol insanda.
- Aynı veri iki ERP'de: özet kartları birebir aynı. Araç katmanı ERP'den bağımsız; yeni bir ERP bir adaptör kadar uzakta.
- Ölçüm: `uv run python scripts/eval.py 3 <senaryo.yaml>` → `reports/` (`ERP_DEFAULT=erpnext` ile ERPNext).

## Olası sorular

- **Canlıya nasıl geçer?** Güçlü makine + daha büyük model; araç katmanı MCP server olarak paketlenir; kullanıcı bazlı Odoo API key ve audit log.
- **Yanlış kayda işlem yaparsa?** Ad belirsizse araç adayları döndürür, model sorar. Onay paneli son kontrol noktası.
- **Neden bulut değil?** KVKK ve ticari sır; internet gerekmiyor.
