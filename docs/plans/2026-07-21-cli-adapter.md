# CLI Adapter Planı

**Tarih:** 2026-07-21
**Amaç:** Veriye TUI klavye + ajan bash üzerinden eşit erişim

## Problem

Mevcut `calendar.json` ve `sessions.json` dosyaları insan dostu değil, ajan için
de kırılgan (schema bilgisi gerekir, atomik yazma yok). Görevler Markdown'da
zaten duruyor.

## Çözüm

Tek format (Markdown), iki erişim yolu (TUI klavye + CLI bash). TUI ve CLI aynı
`storage.py` katmanı üzerinden çalışır, `flock` ile senkronize olur.

## Mimari

```
.todo/
  tasks.md          # zaten var (parser.py kullanıyor)
  calendar.md       # YENİ — calendar.json yerine
  sessions.md       # YENİ — sessions.json yerine
  lock              # flock için boş dosya

todo/
  core/
    models.py
    parser.py                  # tasks.md (mevcut)
    calendar_parser.py         # YENİ — calendar.md parse/build
    sessions_parser.py         # YENİ — sessions.md parse/build
    storage.py                 # flock + atomik yazma
    dashboard_io.py            # uyumluluk için kalsın (TUI henüz taşınmadı)

  cli/
    __init__.py
    main.py                    # argparse dispatcher
    tasks.py                   # namespace + task komutları
    calendar.py                # calendar komutları
    sessions.py                # session komutları
```

## Format

### tasks.md (mevcut, dokunma)

```markdown
# bigg
- ana başvuru hazırla
  - teknik konsept eki yaz
  - PoC çalıştır
- jüri sunumu prova et
```

### calendar.md (yeni)

```markdown
# 2026-07-25
- 09:00–10:00 jüriler
- 14:00–15:00 prova
- 19:00–20:00 sunum

# 2026-07-26
- 10:00–11:30 mentor toplantısı
```

### sessions.md (yeni)

```markdown
# 2026-07-21
- 14:30–15:00 kod yaz (25 dk pomodoro)
- 15:05–15:15 mola

# 2026-07-22
- 09:00–12:00 BİGG çalışması
```

## Lock + Atomik Yazma

`storage.py` her write'ta:

1. `.todo/lock` dosyasını `fcntl.flock(LOCK_EX)` ile kilitler (5 sn timeout).
2. Hedef dosyayı okur.
3. Parse → model değişikliği uygula.
4. Build → temp dosyaya yaz.
5. `os.replace(tmp, hedef)` (atomik rename).
6. Lock'u bırakır.

TUI ve CLI aynı lock'u paylaşır. TUI reload watcher'ı periyodik `os.path.getmtime`
ile dış değişikliği algılar.

## CLI Komut Seti

### Namespace + Task

```
python -m todo.cli task list [--ns NS] [--json]
python -m todo.cli task add --ns NS --text "..."
python -m todo.cli task add-child --ns NS --parent "..." --text "..."
python -m todo.cli task done --ns NS --task "..."
python -m todo.cli task rename --ns NS --task "..." --new "..."
python -m todo.cli task delete --ns NS --task "..." [--cascade]
python -m todo.cli namespace list [--json]
python -m todo.cli namespace create --name NS
```

### Calendar

```
python -m todo.cli calendar today [--json]
python -m todo.cli calendar list --date YYYY-MM-DD [--json]
python -m todo.cli calendar add --date YYYY-MM-DD --start HH:MM --duration MIN --text "..."
python -m todo.cli calendar add-bulk --date YYYY-MM-DD  (stdin'den çoklu)
python -m todo.cli calendar move --id N --to-date ... --to-start HH:MM
python -m todo.cli calendar delete --id N
```

### Sessions

```
python -m todo.cli session start --ns NS --task "..." --duration MIN
python -m todo.cli session stop
python -m todo.cli session log --date YYYY-MM-DD [--json]
```

## Senaryo Simülasyonu (son test)

1. **"25 Temmuz'a şunları koy":**
   ```bash
   python -m todo.cli calendar add-bulk --date 2026-07-25 <<EOF
   09:00 60 jüriler
   14:00 60 prova
   19:00 60 sunum
   EOF
   cat .todo/calendar.md  # doğrulama
   ```

2. **"bigg namespace'inde jüri sunumu prova et'e slayt deck hazırla alt görevi ekle":**
   ```bash
   python -m todo.cli task add-child \
     --ns bigg \
     --parent "jüri sunumu prova et" \
     --text "slayt deck hazırla"
   cat .todo/tasks.md  # doğrulama
   ```

3. **"TUI açıkken ajan yazarsa":**
   TUI arka planda açıkken CLI ile ekle → TUI 2 saniye içinde reload eder
   → ekranda yeni event görünür.

## Migration

İlk çalıştırmada `dashboard_io.py` yerine yeni parser'lar kullanılır. Eski
`calendar.json` ve `sessions.json` dosyaları `.bak` olarak saklanır, kullanıcı
isterse siler.

## Aşamalar

1. Plan dosyası yazıldı (bu).
2. `calendar_parser.py` + `sessions_parser.py` yaz.
3. `storage.py` lock + atomik yazma.
4. `cli/` paketi + komutlar.
5. Migration script'i.
6. TUI reload watcher.
7. Testler.
8. Senaryo simülasyonu.
9. Commit (3-5 commit, mantıksal parçalara bölünmüş).