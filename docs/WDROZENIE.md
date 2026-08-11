# Wdrożenie na VPS — `rspo.silesia3d.site`

Instrukcja do **wykonania**, nie do czytania. Ta sama ścieżka, co przy aplikacji
leadów (`..\leady_app_v5\docs\15_DOMENA_I_WDROZENIE.md`) — tam jest opisana
szerzej, tutaj są **różnice i konkrety RSPO**. Jeśli coś jest niejasne, tamten
dokument jest źródłem; ten go nie zastępuje, tylko dopisuje osobny przypadek.

**Kolejność, której nie wolno odwrócić:**

```
DNS → nslookup → kontener → nginx bez SSL → hasło (htpasswd) → certbot → sprawdzenie
```

DNS idzie pierwszy, bo `certbot` odmówi wystawienia certyfikatu, dopóki domena
nie wskazuje na serwer — Let's Encrypt sprawdza to, pukając z zewnątrz. Odwrócenie
kolejności to godzina czekania i błąd `Timeout during connect`, który wygląda jak
awaria firewalla, a jest niecierpliwością.

---

## 0. Konkrety tego wdrożenia

| Rzecz | Wartość |
|---|---|
| VPS | `ubuntu@57.128.241.52` (OVH) |
| domena | `rspo.silesia3d.site` |
| katalog na serwerze | `/home/ubuntu/apps/rspo.silesia3d.site` |
| repozytorium | `https://github.com/pkonieczny007/rspo_app.git` (prywatne) |
| kontener | `rspo_app`, gunicorn, port kontenera 5000 |
| port na hoście | **`127.0.0.1:5310`** — ten sam numer co lokalnie |
| wolumen z danymi | `rspo_data` → `/data` |
| dostęp | **nginx Basic Auth** — aplikacja nie ma własnego logowania |

Co już stoi na tej maszynie i czego nie ruszamy: `ph.silesia3d.site` (5301),
`demo-ph.silesia3d.site` (5302), `librus.silesia3d.site` (5100). Port 5310
sprawdź przed startem — `ss -tlnp | grep 5310` ma nie pokazać nic.

### Czym to wdrożenie różni się od aplikacji leadów

**1. Jedna usługa, bez demo.** Tam demo było potrzebne, bo klient oglądał
aplikację przed startem i trzeba było mieć gdzie psuć. Tutaj baza odtwarza się
z pliku rejestru w kilka minut, a nasze własne dane siedzą w kopii — więc drugi
kontener byłby drugą rzeczą do aktualizowania bez drugiej korzyści.

**2. Hasło jest w nginx, nie w aplikacji.** RSPO nie ma logowania i to była
świadoma decyzja (CLAUDE.md §5), bo narzędzie chodziło lokalnie u koordynatorki.
Na publicznym adresie ta decyzja przestaje obowiązywać: `/import` przyjmuje
dowolny plik, `/rejony/usun/<id>` kasuje rejon, a `/placowki/objete` przestawia
flagę hurtem — **wszystkie bez żadnego sprawdzenia, kto pyta**. Sam rejestr jest
publiczny, ale to, KTÓRE szkoły klient wziął na cel, już nie.

Basic Auth w nginx załatwia to bez linijki kodu i przeżyje ewentualne dołożenie
PIN-ów później. To jest **plaster, nie docelowe rozwiązanie** — jedno hasło dla
wszystkich, bez wylogowania i bez śladu, kto co zrobił. Docelowo mechanizm PIN-ów
z aplikacji leadów; wtedy wpis `auth_basic` z konfiguracji nginx wypada.

**3. Wgrywany plik ma 42 MB.** Stąd `client_max_body_size 256M` w nginx,
`--timeout 900` w gunicornie i `proxy_read_timeout 900s`. Przy domyślnych
wartościach import kończy się błędem 413 albo 504 w połowie przeliczania.

---

## 1. DNS w OVH — najpierw, i poczekaj

**OVH Manager → Web Cloud → Domeny → `silesia3d.site` → „Strefa DNS" → Dodaj
wpis → typ `A`.**

| Pole | Wartość |
|---|---|
| Subdomena | `rspo` |
| TTL | `1 minuta` (albo `Domyślny`) |
| Cel | `57.128.241.52` |

W polu „Subdomena" wpisuje się **samo `rspo`**, bez domeny — OVH dokleja resztę.
Wpisanie pełnej nazwy daje `rspo.silesia3d.site.silesia3d.site`, a `nslookup`
powie „Non-existent domain" i będziesz sprawdzał IP zamiast literówki.

Nie ruszaj rekordu głównego (`silesia3d.site` → `213.186.33.5`, hosting OVH).
`AAAA` pomijamy — rekord IPv6 wskazujący adres, na którym nginx nie nasłuchuje,
daje objaw „z biura działa, z telefonu po LTE nie".

```powershell
nslookup rspo.silesia3d.site 8.8.8.8      # ma zwrócić 57.128.241.52
```

Pytamy wprost Google, bo domowy router lubi zapamiętać „nie ma takiej domeny"
i uparcie ją powtarzać. Dopóki nie odpowiada poprawnie — punkty 2–4 możesz robić,
punktu 6 (certbot) nie ma sensu nawet zaczynać.

## 2. Kod i sekrety na serwerze

```bash
ssh ubuntu@57.128.241.52
mkdir -p ~/apps && cd ~/apps
git clone https://github.com/pkonieczny007/rspo_app.git rspo.silesia3d.site
cd rspo.silesia3d.site

cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"    # wklej do SECRET_KEY
nano .env
chmod 600 .env
```

Katalog nazwany subdomeną — tak stoi librus i aplikacja leadów, i tak po
miesiącach najłatwiej znaleźć, co obsługuje daną nazwę.

`SECRET_KEY` generuj **na serwerze**, żeby nie przeszedł przez schowek ani
historię poleceń na Twoim komputerze. Domyślna wartość z kodu (`rspo-narzedzie`)
leży na GitHubie.

## 3. Kontener

```bash
docker compose up -d --build rspo
docker compose logs -f rspo                                        # Ctrl+C wychodzi
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5310/    # 200
docker ps --format '{{.Names}}\t{{.Ports}}' | grep rspo            # 127.0.0.1:5310->5000
```

`200` na `127.0.0.1` znaczy, że aplikacja żyje — jeszcze bez domeny, HTTPS
i hasła. Jeśli tu nie ma `200`, żadna konfiguracja nginx tego nie naprawi.

**`docker ps` MUSI pokazać `127.0.0.1:5310->`, a nie `0.0.0.0:5310->`.** Port bez
adresu z przodu jest wystawiony na świat z pominięciem nginx — czyli bez HTTPS
i bez hasła — a `ufw` tego nie zasłoni, bo docker pisze reguły wprost do iptables.
Tak stoi na tej maszynie librus (`0.0.0.0:5100`) i to jest przykład błędu, nie wzór.

Baza siedzi w wolumenie `rspo_data`. `docker compose build` i restart jej nie
ruszają. **Ale `docker compose down -v` kasuje wolumen** — nigdy nie dopisuj `-v`
odruchowo.

## 4. Dane — wgraj gotową bazę, nie importuj na produkcji

Lokalna baza ma już wszystko: 6 116 placówek śląskiego, 17 rejonów Kasi, flagi
„objęta działaniem". Plik waży 4,6 MB, więc przenosi się w sekundę.

Kuszące jest wejść na `/import` na serwerze i wgrać tam 42-megabajtowy plik.
Nie rób tego przy pierwszym uruchomieniu: import na świeżej bazie odtworzy
placówki, ale **nie odtworzy ani jednej naszej decyzji** — flagi `objeta`,
notatki i poszerzone rejony nie występują w żadnym pliku z rspo.gov.pl.

```powershell
# 1. u siebie — kopia bieżącej bazy (spójna, jeden plik, bez WAL)
python narzedzia\kopia.py zrob --trzymaj 0
scp dane\kopie\rspo_*.db ubuntu@57.128.241.52:/tmp/
```

```bash
# 2. na serwerze
cd ~/apps/rspo.silesia3d.site
docker compose stop rspo
docker compose run --rm -v /tmp:/wejscie rspo sh -c \
  'cp /wejscie/rspo_*.db /data/rspo.db && rm -f /data/rspo.db-wal /data/rspo.db-shm'
docker compose start rspo
rm -f /tmp/rspo_*.db

# 3. sprawdź LICZBY, nie sam fakt, że wstało
docker compose exec -T rspo python -c \
  "import db,sqlite3; c=db.polacz(); print('placówki:', c.execute('SELECT COUNT(*) FROM placowki').fetchone()[0]); print('rejony:', c.execute('SELECT COUNT(*) FROM rejony').fetchone()[0]); print('w rejonach:', c.execute('SELECT COUNT(*) FROM placowka_rejon').fetchone()[0])"
```

Ma wyjść **6 116 placówek, 17 rejonów, 2 552 w rejonach** (stan z 11.08.2026).
Inna liczba znaczy, że poszedł nie ten plik — lepiej dowiedzieć się teraz niż
z pytania Kasi „gdzie się podziały moje zaznaczenia".

`docker compose run` nie publikuje portów, więc nie wchodzi w drogę działającej
usłudze.

## 5. nginx + hasło

Najpierw hasło, żeby blok nginx nie zadziałał ani przez sekundę bez niego:

```bash
sudo apt install -y apache2-utils                      # jeśli nie ma htpasswd
sudo htpasswd -c /etc/nginx/.htpasswd-rspo silesia     # zapyta o hasło dwa razy
sudo chmod 640 /etc/nginx/.htpasswd-rspo
sudo chown root:www-data /etc/nginx/.htpasswd-rspo
```

Hasło wpisz **w odpowiedzi na pytanie**, nie w linii poleceń (`htpasswd -b`) —
to drugie zostaje w `~/.bash_history`. Zapisz je w menedżerze haseł; nie ma skąd
go odczytać, plik trzyma tylko skrót.

Potem konfiguracja — wzór leży w repozytorium, więc bez przepisywania z ekranu:

```bash
sudo cp nginx/rspo.silesia3d.site.conf /etc/nginx/sites-available/rspo.silesia3d.site
sudo ln -s /etc/nginx/sites-available/rspo.silesia3d.site /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

`nginx -t` przed każdym `reload` — literówka kładzie **wszystkie** aplikacje na
serwerze, także te, których nie ruszałeś.

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://rspo.silesia3d.site/     # 401
curl -s -o /dev/null -w '%{http_code}\n' -u silesia:HASLO \
     http://rspo.silesia3d.site/                                         # 200
```

**`401` bez hasła to wynik poprawny**, nie błąd — to jedyny dowód, że Basic Auth
naprawdę działa. `200` bez hasła znaczy, że `auth_basic` trafił poza blok
`server` albo plik `.htpasswd-rspo` jest nieczytelny dla nginx.

## 6. certbot — HTTPS

```bash
sudo certbot --nginx -d rspo.silesia3d.site
```

Na pytanie o przekierowanie z HTTP odpowiedz **tak**. Certbot dopisze do pliku
sekcję `listen 443 ssl` i ścieżki do certyfikatów — tych linii nie edytuj ręcznie,
przy odnowieniu i tak zostaną nadpisane.

```bash
systemctl list-timers | grep certbot     # ma być wpis z datą następnego uruchomienia
sudo certbot renew --dry-run             # próba na sucho, bez zużywania limitów
```

Certyfikat żyje 90 dni i nikt o nim nie pamięta w listopadzie. **Portu 80 nie
zamykaj po włączeniu HTTPS** — odnowienie idzie właśnie po nim.

W aplikacji leadów po certbocie ustawiało się `HTTPS=1`. **Tutaj tego kroku nie
ma** — ta zmienna włączała flagę `Secure` na ciastku sesji logowania, a RSPO
sesji nie używa. Nie dopisuj jej „dla symetrii", bo w kodzie nic jej nie czyta
i następna osoba będzie szukała, co robi.

## 7. Kopie zapasowe — cron o 6:15

```bash
crontab -e
```

```cron
15 6 * * * cd /home/ubuntu/apps/rspo.silesia3d.site && docker compose exec -T rspo \
  python narzedzia/kopia.py zrob --trzymaj 30 >> /var/log/rspo_kopia.log 2>&1
```

**6:15, nie 6:00** — o 6:00 chodzi kopia aplikacji leadów na tej samej maszynie;
dwa `docker compose exec` naraz to niepotrzebne ryzyko na jednym dysku.

**`-T` jest konieczne**: bez niego `docker compose exec` chce terminala, a cron
go nie ma — zadanie kończy się cicho błędem i przez tydzień nikt nie zauważy,
że kopii nie ma.

Uruchom raz z ręki, żeby zobaczyć, że kopia powstaje, i **przećwicz odtwarzanie
zanim będzie potrzebne** — kopia, której nigdy nie odtworzono, jest nadzieją:

```bash
docker compose exec -T rspo python narzedzia/kopia.py zrob
docker compose exec -T rspo python narzedzia/kopia.py lista
docker compose exec -T rspo python narzedzia/kopia.py przywroc --z /data/kopie/rspo_….db
```

`przywroc` sam robi kopię stanu bieżącego, zanim cokolwiek nadpisze.

### Ściąganie kopii na swój dysk — dwa kroki, nie jeden

Kopie leżą w wolumenie dockera (`/var/lib/docker/volumes/…`), a ten katalog
należy do `root` i ma prawa `drwx--x---`. Użytkownik `ubuntu` — czyli także
`scp` i eksplorator plików w VS Code — dostaje tam „Permission denied", co łatwo
wziąć za „nie ma kopii". Trzeba je najpierw wyłożyć:

```bash
mkdir -p ~/kopie-rspo && docker cp rspo_app:/data/kopie/. ~/kopie-rspo/
chmod 700 ~/kopie-rspo && chmod 600 ~/kopie-rspo/*
ls -lh ~/kopie-rspo
```

```powershell
scp "ubuntu@57.128.241.52:~/kopie-rspo/*" C:\XEN\AI-szkolenie\SIERPIEN2026\kopie_vps\rspo\
```

```bash
rm -rf ~/kopie-rspo          # posprzątaj po sobie
```

**Kopia leżąca na tym samym serwerze co oryginał nie jest kopią zapasową** —
chroni przed pomyłką człowieka, nie przed awarią maszyny. Docelowo ten katalog
ciągnie Mac mini razem z bazą leadów (`..\leady_app_v5\docs\17_KOPIE_NA_MACU.md`);
dopisanie RSPO do tamtego skryptu to osobna, mała robota.

### Wgrane pliki rosną

`/data/wgrane/` trzyma **każdy** wgrany plik ze znacznikiem czasu — celowo, żeby
dało się wrócić do *tego* pliku, gdy raport pokaże coś dziwnego. Ale to 42 MB
miesięcznie w wolumenie, którego nikt nie ogląda. Raz na pół roku:

```bash
docker compose exec -T rspo sh -c 'ls -lh /data/wgrane | tail -5; du -sh /data'
```

## 8. Aktualizacja później

```bash
cd ~/apps/rspo.silesia3d.site && ./wdroz.sh
```

Robi kopię, `git pull`, przebudowę, sprawdza `200` i **sprawdza, czy port dalej
jest na 127.0.0.1**. Ostatnie z nich nie jest paranoją: to jedna literówka
w `docker-compose.yml` i nic tego samo nie zgłosi.

---

## Grabie

**Gunicorn nie wykonuje `main()`.** Schemat bazy i rejony startowe zakłada
`przygotuj_baze()` wywoływane **przy imporcie modułu** `app.py`. Gdyby ktoś
przeniósł to z powrotem do `main()` „bo tam jest start", na serwerze pierwsze
wejście skończy się `no such table: placowki` — komunikatem, który wygląda na
zepsute wdrożenie, a jest brakującą linijką.

**`RSPO_DATA`, nie `DATA_DIR`.** Aplikacja leadów czyta `DATA_DIR` i to jest
tamta zmienna. Tutaj `db.py` czyta `RSPO_DATA` (oraz `RSPO_DB`). Wpisanie
`DATA_DIR` do `docker-compose.yml` nie zrobi nic — baza wyląduje w `/app/dane`,
czyli w kontenerze, i **zniknie przy pierwszej przebudowie**. Objawi się to jako
„gdzie się podziały dane", a nie jako błąd.

**Port publikowany bez `127.0.0.1` omija ufw.** Patrz punkt 3 — to nie teoria,
tak stoi sąsiedni librus.

**`docker compose down -v` kasuje bazę.** Bez `-v` kontener można wywalać do woli.

**413 z nginx zamiast komunikatu aplikacji.** Domyślny `client_max_body_size` to
1 MB, a plik rejestru ma 42 MB. Aplikacja ma własny, polski komunikat o zbyt
dużym pliku (limit 250 MB) — żeby użytkownik go zobaczył, sufit nginx musi być
wyższy. Stąd 256M.

**504 w połowie importu.** Przeliczenie 56 190 wierszy trwa. `proxy_read_timeout`
w nginx i `--timeout` gunicorna muszą być OBA długie — krótszy z nich decyduje,
a użytkownik po 504 wgra plik drugi raz, w trakcie pierwszego.

**Certbot przed DNS-em.** Objaw: `Timeout during connect (likely firewall
problem)`. Firewall nie ma z tym nic wspólnego. **5 nieudanych prób na godzinę
dla tej samej nazwy blokuje ją na godzinę** — tego nie da się „przeklikać".

**`grep -r` nie wchodzi w dowiązania.** `sites-enabled` to same dowiązania, więc
`grep -rn "rspo" /etc/nginx/sites-enabled/` nic nie znajdzie, choć konfiguracja
tam jest. Szukaj przez `sudo nginx -T` albo `grep -Rn` z wielkim `R`.

---

## Checklista

- [ ] w OVH rekord `A`: `rspo` → `57.128.241.52`
- [ ] `nslookup rspo.silesia3d.site 8.8.8.8` zwraca `57.128.241.52`
- [ ] `ss -tlnp | grep 5310` nie pokazuje niczego (port wolny)
- [ ] `git clone`, `.env` z własnym `SECRET_KEY`, `chmod 600 .env`
- [ ] kontener wstaje, `curl` na 5310 daje `200`
- [ ] `docker ps` pokazuje `127.0.0.1:5310->`, **nie** `0.0.0.0:`
- [ ] baza przeniesiona z lokalnej: **6 116 placówek, 17 rejonów, 2 552 w rejonach**
- [ ] `htpasswd` założony, hasło w menedżerze haseł
- [ ] nginx: `nginx -t` czysty, **`401` bez hasła**, `200` z hasłem
- [ ] `certbot`, przekierowanie na HTTPS włączone, `renew --dry-run` przechodzi
- [ ] cron 6:15 + jedno uruchomienie z ręki, żeby zobaczyć plik kopii
- [ ] próba **przywrócenia** kopii (nie samego zrobienia)
- [ ] wgranie pliku 42 MB przez `/import` na serwerze przechodzi bez 413 i 504
- [ ] pobranie wykazu XLSX z `/eksport` otwiera się w Excelu
