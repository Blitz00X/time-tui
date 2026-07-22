# GNOME Top Bar Extension Planı

**Tarih:** 2026-07-22
**Amaç:** time-tui tracker session'ını GNOME top bar'da göster. TUI alta
alındığında bile aktif session'ın durumunu görebil.

## Problem

TUI tracker (pomodoro + stopwatch + focus) terminalde çalışıyor. Terminal
alta alınınca (veya başka bir workspace'e geçince) aktif session'ın kalan
süresini görmek imkansız. Bu, zaman yönetimi workflow'unu kırıyor.

## Çözüm (yüksek seviye)

TUI bir **DBus servisi** olarak aktif session state'ini export eder. Ayrı
bir **GNOME Shell extension** bu state'i okur ve top bar'a küçük bir sayaç
yerleştirir. Tıklanınca popup'ta detay görünür. TUI kapandığında
extension "TUI çalışmıyor" mesajı gösterir — graceful degradation.

```
┌─────────────────────────────────────────────────────────┐
│  GNOME top bar:  [  25:00 • kod yaz  ▼ ]               │
│                       │                                  │
│                       └── popup:                         │
│                            ┌──────────────────────────┐ │
│                            │ aktif: kod yaz           │ │
│                            │ kalan: 12:34             │ │
│                            │ [Duraklat]               │ │
│                            │ ─────────                │ │
│                            │ bugün:                   │ │
│                            │  09:00–11:30 BİGG       │ │
│                            │  14:30–15:00 kod yaz    │ │
│                            └──────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## Mimari

```
time-tui (Textual app)
   ├─ PomodoroTracker (mevcut state)
   └─ DBusService (yeni)  ─── exports ──→  Session bus
                                                    │
                                                    ▼
                              GNOME Shell extension (timetui-topbar@kutay)
                                  ├─ TopBarLabel: [25:00 • kod yaz]
                                  └─ PopupMenu (tıklanınca)
```

## Bileşenler

### 1. DBus servisi (`todo/core/dbus_service.py`)

**Kütüphane:** `jeepney` (pure-Python, GLib bağımlılığı yok). TUI'ın ana
loop'unu bloklamaz, kendi thread'inde çalışır.

**Wire format:**

```
Service name:    org.timetui.Session
Object path:     /org/timetui/Session
Interface name:  org.timetui.Session

Methods:
  dict Get()            → aktif session state (yoksa {'active': False})
  list  List(date_str) → bugünkü veya verilen tarihin session log'u
  void  Pause()         → aktif session'ı duraklat (DBus → TUI callback)
  void  Resume()        → aktif session'ı devam ettir
  void  Stop()          → aktif session'ı bitir

Signals:
  Updated(dict state)   → state her değiştiğinde yayınlanır
```

**State dict yapısı:**

```python
{
    "active": True,
    "kind": "pomodoro",         # pomodoro | stopwatch | focus
    "label": "kod yaz",
    "namespace": "bigg",
    "started_at": "2026-07-22T14:30:00",
    "duration_sec": 1500,
    "remaining_sec": 723,
    "elapsed_sec": 777,
    "progress": 0.518,
    "paused": False,
}
```

**TUI entegrasyonu:**
- `TimeTuiApp.on_mount` → `DBusService(self).start()`
- `TimeTuiApp.on_unmount` → `service.stop()`
- Service, her saniye `Updated` sinyali yayar (sentinel tick) — aktif
  session olmasa bile, extension "TUI çalışıyor ama boşta" durumunu
  ayırt edebilir.

**Graceful degradation:** DBus bağlantısı kurulamazsa (örn. headless
ortam, SSH session) TUI sessizce devam eder. Hiçbir hata atmaz.

### 2. Bildirim servisi (`todo/core/notify.py`)

GNOME `org.freedesktop.Notifications` interface'i üzerinden `notify-send`
benzeri wrapper. Session bittiğinde veya milestone'larda (yarısı doldu,
5 dk kaldı) tetiklenir. DBus bağımlılığı yine `jeepney`.

**Fonksiyon:** `notify(summary: str, body: str, urgency: str = "normal")`

**Milestone'lar:**
- Session %50 dolduğunda → "yarısı kaldı"
- Son 5 dakika → "5 dakika kaldı"
- Session bitti → "pomodoro bitti" (kısa bir pause sonrası yeni pomodoro
  önerisi)

### 3. GNOME extension (`extensions/timetui-topbar/`)

```
extensions/timetui-topbar/
├── metadata.json
├── extension.js
├── prefs.js              # opsiyonel, v2'de
├── stylesheet.css
├── README.md
└── install.sh            # extension'ı ~/.local altına kopyalar
```

**`metadata.json`:**

```json
{
  "uuid": "timetui-topbar@kutay",
  "name": "time-tui Tracker",
  "description": "Show active time-tui tracker session in the top bar.",
  "shell-version": ["45", "46", "47"],
  "version": 1,
  "session-modes": ["user", "wayland", "x11"]
}
```

**`extension.js`** (özet):

```js
const GET = Gio.DBus.session.call(...);  // her saniye
// veya Updated signal'i dinle
const conn = Gio.DBus.session.signal_subscribe(
  null, 'org.timetui.Session', 'Updated', '/org/timetui/Session',
  null, Gio.DBusSignalFlags.NONE, onUpdated, null
);

// Top bar'a Label ekle
const label = new St.Label({ text: '⏱ …', y_align: Clutter.ActorAlign.CENTER });
Main.panel.addToStatusArea('time-tui-tracker', label, 0, 'right');

// Tıklama popup'ı
const menu = new PopupMenu.PopupMenu(label, 0.5, St.Side.TOP);
const popupItem = new PopupMenu.PopupBaseMenuItem();
const box = new St.BoxLayout({ vertical: true });
// ... label, progress bar, session listesi
```

**Önemli noktalar:**
- `panel.addToStatusArea` ile top bar'a eklenir (sağ taraf, sistem
  menüsünün soluna).
- Click handler `popup-menu`'yu açar.
- DBus `call` timeout'lu (2s) — TUI kapalıysa extension "TUI yok" yazar.
- Extension reload'a dayanıklı (disable+enable sonrası temiz state).

### 4. Kurulum (`extensions/timetui-topbar/install.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

UUID="timetui-topbar@kutay"
DEST="$HOME/.local/share/gnome-shell/extensions/$UUID"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$DEST"
cp "$HERE"/{metadata.json,extension.js,stylesheet.css,README.md} "$DEST/"
chmod +r "$DEST"/*

# Session bus üzerinde test servis adı (sadece development)
echo "Installed to $DEST"
echo "Next: enable with 'gnome-extensions enable $UUID' and reload GNOME Shell (Alt+F2 → r)"
```

## Dosya envanteri (eklenen / değişen)

```
todo/core/dbus_service.py        YENİ — DBus service + state marshaling
todo/core/notify.py              YENİ — notification helper
todo/ui/app.py                   değişir — service'i başlat/durdur
todo/tests/test_dbus_service.py  YENİ — DBus unit + integration tests
todo/tests/test_notify.py        YENİ — notification testleri (mock)

extensions/timetui-topbar/
├── metadata.json                YENİ
├── extension.js                 YENİ
├── stylesheet.css               YENİ
├── README.md                    YENİ
└── install.sh                   YENİ
```

## Bağımlılıklar

`pyproject.toml`'a:

```toml
[project.optional-dependencies]
dbus = ["jeepney>=0.8.0"]
```

Default kurulumda `dbus` opsiyonel. `uv sync --group dbus` ile veya
`uv sync --all-extras` ile yüklenir.

## Test stratejisi

### DBus unit testleri (`test_dbus_service.py`)

TUI'sız, mock tracker ile:

1. **Service başlatma:** `DBusService.start()` sonra `session_bus` üzerinde
   `org.timetui.Session` adı yayında mı?
2. **Get():** aktif session yokken `{'active': False}` döner mi?
3. **Get():** aktif session varken doğru state dict döner mi?
4. **Updated sinyali:** tracker state'i değişince DBus sinyali yayınlanıyor
   mu? (signal_subscribe ile dinle, count et)
5. **Pause/Resume/Stop:** callback zinciri doğru mu?
6. **Cleanup:** `stop()` sonrası servis adı bus'tan kalkıyor mu?
7. **Graceful degradation:** DBus yokken start() exception atmıyor mu?

Integration test: gerçek jeepney + GLib yerine, isolated bir sahte bus
üzerinde çalıştır. `dbus_next` test pattern'i veya jeepney'ın kendi
testing yardımcısı.

### Notification testleri (`test_notify.py`)

`notify()` çağrısı doğru DBus mesajı üretiyor mu? Mock'la.

### Extension testi (manuel)

`install.sh` çalıştır, GNOME Shell reload, top bar'da label görünüyor mu:
- TUI kapalıyken "TUI yok" mesajı
- TUI açık + pomodoro çalışırken "25:00 • kod yaz"
- Pomodoro duraklatılınca "⏸ 12:34 • kod yaz"
- Tıklanınca popup açılıyor, bugünkü session listesi görünüyor

Xephyr veya gerçek GNOME session'da validate edilebilir. CI'da extension
testi yapılmaz (GNOME gerekli).

## Aşamalar (sıralı)

1. **DBus service:** `dbus_service.py`, Get/Updated/Pause/Resume/Stop,
   jeepney ile, bağlantı kurulmazsa graceful skip.
2. **Notify:** `notify.py`, jeepney, milestone entegrasyonu (mevcut
   pomodoro state machine'ine event hook).
3. **TUI entegrasyonu:** `app.py` on_mount/on_unmount'ta service'i
   başlat/durdur, milestone event'lerini notify'ye bağla.
4. **Unit + integration testler:** iki test dosyası, gerçek DBus loop
   üzerinden.
5. **GNOME extension skeleton:** `metadata.json`, `extension.js`,
   `stylesheet.css`, DBus bağlantısı + top bar label.
6. **Popup menu:** tıklama popup'ı, bugünkü session listesi.
7. **Kurulum scripti ve README:** `install.sh`, kullanım talimatları.
8. **Manuel doğrulama:** Xephyr + GNOME Shell veya gerçek session,
   uçtan uca test.
9. **Commit (3 commit):** core (dbus + notify + tests), extension,
   install + docs.

## Validation / kabul kriterleri

- [ ] TUI açıkken DBus introspection ile `org.timetui.Session` görünür.
- [ ] `Get()` çağrısı aktif state'i dict olarak döner.
- [ ] `Updated` sinyali her saniye yayınlanır.
- [ ] `Pause`/`Resume`/`Stop` çağrıları tracker state'ini değiştirir.
- [ ] TUI kapandığında DBus adı bus'tan kalkar (komşu process'leri
      etkilemez).
- [ ] DBus olmayan ortamda TUI normal çalışır, hata loglamaz.
- [ ] `notify()` ile bildirim gelir (gerçek GNOME session'da veya
      `gdbus call` ile doğrulanır).
- [ ] Extension `install.sh` sonrası `gnome-extensions list --enabled`
      çıktısında görünür.
- [ ] Top bar'da sayaç belirir, TUI kapandığında "—" yazar.
- [ ] Tıklanınca popup açılır, session listesi görünür.
- [ ] Tüm unit + integration testler geçer (`pytest -q`).
- [ ] Mevcut 164 test bozulmaz.

## Riskler / geri dönüş

- **Jeepney GLib ile çakışma:** bağımsız thread kullanırız, TUI event
  loop'una dokunmayız. Sorun olursa `python-dbus` (gi.repository) ile
  geçiş yaparız — daha yaygın ama GLib mainloop gerektirir.
- **GNOME sürüm uyumsuzluğu:** metadata.json'da `[45, 46, 47]` ile
  başlarız. Çalışmazsa sürümü düşürürüz.
- **Wayland DBus kısıtlaması:** standart session bus'a bağlanır,
  uygulama sandboxing yok. Bu bizim case'imizde sorun değil.
- **Bildirim spam:** milestone debouncing (her milestone için session
  başına en fazla 1 bildirim).

## Kapsam dışı (v2'ye bırakıldı)

- Extension ayarlar paneli (prefs.js) — kısayol, görünüm ayarları
- Action butonları (popup'tan pause/resume) — sadece görüntü v1'de
- Multiple namespace desteği (her biri ayrı top bar label) — v2
- TUI daemon modu (`todotui --daemon`) — uzantı TUI kapalıyken de çalışsın
- macOS / Windows bildirimleri — GNOME'a odaklanıyoruz