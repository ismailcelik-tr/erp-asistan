# Demo runbook

## Hazırlık (demodan 15 dk önce)

```bash
cd ~/Desktop/erp-asistan
docker compose up -d
scripts/reset_demo.sh            # temiz veri (SEED_DATASET), ~1 dk
pgrep -qf "LM Studio" && lms ps; ollama ps   # model yüklü olmasın (16 GB RAM); lms ps kapalı LM Studio'yu başlatır
uv run erp-asistan               # http://localhost:7860
```

- Odoo: http://localhost:8069/odoo?db=erp → `admin` / `admin`
- İki pencere yan yana: solda asistan, sağda Odoo. Asistan yarım ekranda tek sütun çalışır.
- Başlıktaki iki ışık (Yapay Zeka, ERP) yeşil yanıp sönmeli.
- Isınma: ilk komut modeli belleğe yükler (~15 sn). Demodan önce bir sorgu çalıştırın, Yeni sohbet'e basın, sonra `rm history/*.json` (ısınma geçmişte görünmesin).
- Mikrofon ve kamera izinlerini tarayıcı ilk kullanımda sorar; önceden verin.
- Bellek: Docker Desktop 3 GB ile sınırlı. `memory_pressure` %20'nin altındaysa gereksiz uygulamaları kapatın.

## Arayüz

- **Konuş**: basın, konuşun, tekrar basın. Ya da metin kutusu dışında Boşluk tuşunu basılı tutun. Esc iptal eder.
- Her araç çağrısı bir LED satırı: yeşil tamamlandı, amber onay bekliyor, kırmızı vazgeçildi veya denetim uyarısı. Satıra tıklayınca parametre ve sonuç görünür.
- Boş ekranda tanıtım, ERP özeti ve örnek komutlar. Tıklanan komut yazma alanına gelir; Gönder ile çalışır.
- Sol panel: Yeni sohbet, Fatura oku, geçmiş sohbetler (salt okunur) ve Yardım. ☰ ile kapanır; dar ekranda çekmece olur.
- **Fatura oku**: görseli bırakın, yapıştırın veya kamerayla çekin. Toplamlar ya da tarih tutmazsa "Odoo'ya işle" kilitli kalır.

## Akılda kalacak mesajlar

- Model ERP'ye doğrudan erişmiyor; 13 dar kapsamlı araç kullanıyor. Her yazma işlemi insan onayından geçiyor.
- Hesap yapmıyor: toplamlar, dönem farkları ve tarih dönüşümleri kodda. Model bu işlerde ölçülebilir hata yapıyordu.
- Kendi hatasını gizleyemiyor: araç çağırmadan "oluşturuldu" derse denetim yakalıyor.
- Fatura okumada çapraz kontrol var; ama her okuma hatasını yakalamaz. Son kontrol insanda.
- Ölçüm: `uv run python scripts/eval.py 3 <senaryo.yaml>` → `reports/`.

## Olası sorular

- **Canlıya nasıl geçer?** Güçlü makine + daha büyük model; araç katmanı MCP server olarak paketlenir; kullanıcı bazlı Odoo API key ve audit log.
- **Yanlış kayda işlem yaparsa?** Ad belirsizse araç adayları döndürür, model sorar. Onay paneli son kontrol noktası.
- **Neden bulut değil?** KVKK ve ticari sır; internet gerekmiyor.
