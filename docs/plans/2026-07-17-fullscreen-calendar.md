# Full-screen Calendar Implementation Plan

Goal: Dashboard içindeki sıkışık calendar özetini korurken Day, Week ve Month görünümleri için tam ekran bir çalışma alanı sağlamak.

Architecture:
- `FullCalendarScreen`, dashboard'dan bağımsız bir Textual `Screen` olur.
- Dashboard ve tam ekran görünüm aynı `dashboard_io.load_events()` veri kaynağını kullanır.
- Ekran kapanırken seçili tarih, sekme ve daily başlangıç saati dashboard'a geri aktarılır.
- Dashboard calendar alt çubuğundaki `Full calendar` butonu ekranı açar.

Interaction:
- Dashboard: `Full calendar` butonu veya büyük `C` kısayolu tam ekran calendar'ı açar.
- Full screen: `Escape` geri döner; `D/W/M` görünüm değiştirir; sol/sağ önceki/sonraki dönem; `T` bugüne döner; `A` seçili güne etkinlik ekler.
- Toolbar butonları aynı işlemleri mouse ile sunar.

Layout:
- Day: tüm gün saat satırları, etkinlik blokları ve seçili tarih.
- Week: saat ekseni + yedi gerçek gün sütunu.
- Month: hafta başlıkları + 7x6 hücre grid'i; hücrelerde gün ve ilk etkinlikler.

Validation:
- Açma/kapatma ve state aktarımı testi.
- Day/Week/Month yapısal render testleri.
- Tarih navigasyonu testi.
- Event verisinin tam ekran görünümde görünmesi testi.
- Mevcut dashboard testlerinde regresyon kontrolü.
