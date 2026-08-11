# Wniosek o dostęp do API RSPO — szkic maila (11.08.2026)

Do wysłania po uzupełnieniu pól `[...]`. Załącznik: wypełniony i podpisany
`Wniosek.pdf` (wzór CIE, jest w `tmp/zrodla/`).

**Do:** rspo@cie.gov.pl
**Temat:** Wniosek o dostęp do API [PEŁNA NAZWA SPÓŁKI — SILESIA 3D]

---

Szanowni Państwo,

zgodnie z procedurą opisaną na stronie https://api.rspo.gov.pl/ oraz z §2
Regulaminu korzystania z usługi API Wyszukiwarki RSPO, składam wniosek
o przyznanie dostępu do API Wyszukiwarki RSPO.

**Dane identyfikacyjne podmiotu**
- Nazwa: [PEŁNA NAZWA SPÓŁKI]
- Adres siedziby: [ULICA, KOD, MIASTO]
- NIP: [NIP] · REGON: [REGON]

**Osoba kontaktowa / odpowiedzialna technicznie za integrację**
- Imię i nazwisko: [IMIĘ NAZWISKO]
- Stanowisko: [STANOWISKO]
- E-mail: [MAIL] · Telefon: [TELEFON]

**Cel korzystania z API i opis planowanego wykorzystania**
Prowadzimy działalność edukacyjną skierowaną do przedszkoli, szkół podstawowych
i placówek wychowania pozaszkolnego na terenie województwa śląskiego.
Utrzymujemy własną aplikację wspierającą pracę koordynatora i przedstawicieli
(baza placówek, przypisanie do rejonów działania, historia kontaktu).
Dane z RSPO służą nam do zbudowania i utrzymania aktualnego wykazu placówek:
nazwy, adresu, danych kontaktowych, typu placówki, organu prowadzącego,
kodów TERYT oraz geolokalizacji — tak, aby przy zmianie nazwy lub adresu
placówki nasz rekord aktualizował się automatycznie po numerze RSPO, zamiast
być przepisywany ręcznie z wyszukiwarki. Dane wykorzystujemy wyłącznie
wewnętrznie, nie udostępniamy ich dalej ani nie publikujemy.

**Zakres wymaganych uprawnień:** dostęp tylko do odczytu (GET).

**Aplikacja / system, w którym API będzie używane**
Wewnętrzna aplikacja webowa (Python / Flask, baza SQLite), pobierająca dane
zaplanowanym, ręcznie uruchamianym odświeżeniem, bez ruchu ciągłego.

**Rodzaj pobieranych danych:** dane placówek oświatowych województwa śląskiego
z zasobu `/api/placowki/` oraz słowniki (typy placówek, statusy publiczno-prawne,
kategorie uczniów, etapy edukacji, TERYT). Nie planujemy wysyłania danych do API.

**Przewidywana liczba zapytań:** ok. 100–200 zapytań przy jednym odświeżeniu,
wykonywanym raz w miesiącu — deklarujemy do 2 000 zapytań miesięcznie.

**Oświadczenia**
Oświadczam, że zapoznałem/am się z Regulaminem korzystania z usługi API
Wyszukiwarki RSPO i akceptuję jego postanowienia, zobowiązuję się do
przestrzegania zasad bezpieczeństwa i ochrony danych oraz wyrażam zgodę na
przetwarzanie danych osobowych w celu obsługi wniosku.

W załączeniu podpisany wniosek na wzorze udostępnionym przez CIE.

Z poważaniem,
[IMIĘ NAZWISKO], [STANOWISKO]
[NAZWA SPÓŁKI] · [TELEFON] · [MAIL]

---

## Do uzupełnienia przed wysłaniem

- [ ] dane rejestrowe spółki (adres, NIP, REGON)
- [ ] kto podpisuje `Wniosek.pdf` — osoba uprawniona do reprezentacji
- [ ] czy podajemy adres produkcyjny aplikacji (ph.silesia3d.site) — nie jest
      wymagany, ale uwiarygodnia opis

## Uwaga do treści

Regulamin §3.4 zabrania używania API „do celów niezgodnych z wnioskiem".
Opis wykorzystania powyżej jest **celowo szeroki** (baza placówek + kontakt
+ rejonizacja + geolokalizacja), żeby późniejsza mapa rejonów albo rozszerzenie
na sąsiednie województwo nie wymagały nowego wniosku.
