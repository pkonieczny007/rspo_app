# -*- coding: utf-8 -*-
"""
Eksport wykazu do XLSX.

DWA FORMATY, DWA RÓŻNE ZASTOSOWANIA

„wykaz” — osiem kolumn, dokładnie te, które rozumie `importer.NAGLOWKI_RSPO`
w `leady_app_v5`. To jest DZISIEJSZY sposób podpięcia obu narzędzi: tutaj
wybierasz rejony i typy, plik idzie do aplikacji leadów przez „↑ Import →
źródło RSPO → tryb dopisz”, a dopasowanie po numerze RSPO sprawia, że ponowne
wgranie tego samego pliku niczego nie zdubluje. Zero nowego kodu po stronie
aplikacji leadów — dlatego to działa od pierwszego dnia, zanim powstanie
jakakolwiek integracja przez bazę.

„pełny” — wszystko, co mamy: liczba uczniów, organ prowadzący, publiczność,
podmiot nadrzędny, kod pocztowy, www, rejon. Do obejrzenia w Excelu, do analiz
i do rozmowy z klientem. NIE do importu w aplikacji leadów — ma kolumny
„Gmina” i „Miejscowość”, które tamten importer mapuje na to samo pole.
"""
import db
import zapytania

NAGLOWKI_WYKAZU = ["Nr RSPO", "Nazwa", "Typ", "Miejscowość", "Adres",
                   "Telefon", "E-mail", "Dyrektor"]

# Kolumny formatu pełnego — w kolejności czytelnej dla człowieka, nie w kolejności
# z pliku rejestru (tam numer TERYT stoi między gminą a ulicą).
PELNY = [
    ("Nr RSPO", "rspo"), ("Nazwa", "nazwa"), ("Typ", "typ"), ("Rejon", "rejon_nazwa"),
    ("Powiat", "powiat"), ("Gmina", "gmina"), ("Miejscowość", "miejscowosc"),
    ("Adres", "adres"), ("Kod pocztowy", "kod_pocztowy"),
    ("Telefon", "telefon"), ("E-mail", "email"), ("Strona www", "www"),
    ("Dyrektor", "dyrektor"),
    ("Uczniów", "liczba_uczniow"), ("Publiczność", "publicznosc"),
    ("Organ prowadzący", "organ_nazwa"), ("Typ organu", "organ_typ"),
    ("Miejsce w strukturze", "miejsce_w_strukturze"),
    ("RSPO nadrzędnego", "rspo_nadrzedny"), ("Podmiot nadrzędny", "nazwa_nadrzedna"),
    ("Kategoria uczniów", "kategoria_uczniow"), ("Specyfika", "specyfika"),
    ("REGON", "regon"), ("Objęta działaniem", "objeta"),
    ("Pierwszy import", "pierwszy_import"), ("Ostatni import", "ostatni_import"),
    ("Nieobecna w rejestrze od", "nieobecna_od"),
]


def zapisz(conn, filtry, sciezka, format_="wykaz"):
    """Zapisuje wynik TYCH SAMYCH filtrów, które widać na ekranie. Zwraca liczbę wierszy."""
    import openpyxl

    wiersze, _razem, _p = zapytania.placowki(conn, filtry, wszystko=True)
    wb = openpyxl.Workbook()
    ws = wb.active

    if format_ == "wykaz":
        ws.title = "RSPO"
        ws.append(NAGLOWKI_WYKAZU)
        for w in wiersze:
            ws.append([w["rspo"], w["nazwa"], w["typ"], w["miejscowosc"], w["adres"],
                       w["telefon"], w["email"], w["dyrektor"]])
        szerokosci = (10, 60, 30, 22, 34, 16, 32, 26)
    else:
        ws.title = "Placówki"
        ws.append([h for h, _k in PELNY])
        for w in wiersze:
            ws.append([_wartosc(w, k) for _h, k in PELNY])
        szerokosci = (10, 58, 30, 20, 18, 18, 20, 30, 12, 16, 30, 30, 26,
                      9, 14, 40, 18, 24, 12, 40, 18, 18, 14, 10, 13, 13, 16)

    for i, szer in enumerate(szerokosci, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = szer
    ws.freeze_panes = "A2"
    wb.save(sciezka)
    return len(wiersze)


def _wartosc(w, klucz):
    if klucz == "objeta":
        return "tak" if w.get("objeta") else ""
    return w.get(klucz)


def nazwa_pliku(filtry, format_):
    """Nazwa mówiąca, co jest w środku — plik trafi do maila i do folderu klienta."""
    czesci = ["wykaz_rspo" if format_ == "wykaz" else "placowki_rspo"]
    if filtry.get("rejon", "").isdigit():
        czesci.append("rejon")
    elif filtry.get("rejon") == "brak":
        czesci.append("poza-rejonami")
    if filtry.get("grupa") == "nasze":
        czesci.append("nasze-typy")
    elif filtry.get("grupa"):
        czesci.append(filtry["grupa"])
    if filtry.get("powiat"):
        czesci.append(filtry["powiat"].lower().replace(" ", "-"))
    czesci.append(db.dzis())
    return "_".join(czesci) + ".xlsx"
