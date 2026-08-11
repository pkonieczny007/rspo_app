# -*- coding: utf-8 -*-
"""
Wgrywanie pliku do bazy — i jedyne miejsce, w którym powstają albo nie powstają
duplikaty.

ZASADA: PLIK JEST OBRAZEM REJESTRU, BAZA JEST JEGO LUSTREM
Każde wgranie robi trzy rzeczy i tylko trzy:
  1. czego nie było — dopisuje (`nowa`)
  2. co się zmieniło — nadpisuje i zapisuje w dzienniku, co dokładnie (`zmieniona`)
  3. czego w pliku zabrakło — OZNACZA jako nieobecne w rejestrze, nie kasuje

Duplikat nie może powstać, bo `rspo` jest kluczem głównym tabeli. To nie jest
staranność w kodzie, którą da się przeoczyć przy następnej poprawce — to
warunek narzucony przez bazę.

DLACZEGO NIE KASUJEMY ZNIKNIĘTYCH
Placówka znika z rejestru także wtedy, gdy się przekształci albo połączy
z inną. W aplikacji leadów wisi na niej historia kontaktów i umówione DT.
Kasowanie jest nieodwracalne, oznaczenie — nie. Znikniętą widać na liście
z filtrem „zniknęły z rejestru”, można ją obejrzeć i zdecydować.

BEZPIECZNIK PRZY WYKRYWANIU ZNIKNIĘĆ
Gdyby ktoś wgrał plik przefiltrowany w wyszukiwarce (np. same Katowice),
naiwne porównanie oznaczyłoby całą resztę województwa jako „zniknęła
z rejestru”. Dlatego zniknięcia liczymy tylko wtedy, gdy plik obejmuje ten sam
zakres, co baza, a jeśli miałoby zniknąć więcej niż `PROG_ZNIKNIEC` bazy —
wstrzymujemy się i mówimy o tym wprost. Lepszy komunikat niż cicha katastrofa.
"""
import time

import db
import plik as plik_mod
import rejony

# Bezpiecznik odpala się dopiero, gdy zniknięcia są JEDNOCZEŚNIE liczne
# względnie i bezwzględnie. 20%: przy comiesięcznym odświeżeniu realny ubytek
# to promile, a nie co piąta placówka. 25 sztuk: przy małej bazie (pierwsze
# próby na kilkunastu rekordach) sam procent odpalałby się przy każdym
# normalnym ubytku i nikt by nie zobaczył, że mechanizm w ogóle działa.
PROG_ZNIKNIEC = 0.20
MIN_ZNIKNIEC = 25

# Ile zmian pól zapisujemy do dziennika przy jednym imporcie. Przy pierwszym
# wgraniu zmian nie ma (wszystko jest nowe), przy kolejnych to kilkadziesiąt
# wierszy. Limit jest zabezpieczeniem przed dziennikiem na 200 tysięcy wierszy,
# gdyby rejestr kiedyś przestawił format zapisu jakiegoś pola.
LIMIT_ZMIAN = 5000


def wgraj(sciezka, nazwa_pliku, wojewodztwo=db.WOJEWODZTWO_DOMYSLNE,
          wykryj_znikniete=True, conn=None):
    """
    Wgrywa plik i zwraca raport (słownik do pokazania na ekranie).

    `wojewodztwo=None` → cała Polska.
    """
    start = time.time()
    wlasny = conn is None
    conn = conn or db.polacz()
    try:
        wiersze, stat = plik_mod.czytaj(sciezka, wojewodztwo=wojewodztwo)
        zakres = wojewodztwo or "cała Polska"
        dzis = db.dzis()

        # Stan sprzed importu — tylko pola śledzone, żeby nie ciągnąć całej
        # tabeli do pamięci przy pliku ogólnopolskim.
        kolumny = ["rspo"] + db.POLA_SLEDZONE + ["nieobecna_od"]
        przed = {}
        for w in conn.execute("SELECT %s FROM placowki" % ", ".join(kolumny)):
            przed[w["rspo"]] = dict(w)

        nowe, zmienione, bez_zmian, wrocilo = [], [], 0, 0
        dziennik = []

        # Wszystko poniżej leci w JEDNEJ transakcji (sqlite3 otwiera ją sam przy
        # pierwszym zapisie, zamykamy jednym `commit` na końcu). Przy 6 tysiącach
        # wierszy to różnica między ułamkiem sekundy a kilkoma minutami — każdy
        # osobny commit to osobne dotknięcie dysku.
        for r in wiersze:
            stary = przed.get(r["rspo"])
            if stary is None:
                _wstaw(conn, r, dzis)
                nowe.append(r["rspo"])
                continue

            roznice = [(p, stary.get(p), r.get(p))
                       for p in db.POLA_SLEDZONE
                       if _inne(stary.get(p), r.get(p))]
            wrocila = stary.get("nieobecna_od") is not None
            if wrocila:
                wrocilo += 1

            if roznice or wrocila:
                _aktualizuj(conn, r, dzis, roznice, wyczysc_nieobecnosc=wrocila)
                if roznice:
                    zmienione.append(r["rspo"])
                    for pole, bylo, jest in roznice[:20]:
                        if len(dziennik) < LIMIT_ZMIAN:
                            dziennik.append((r["rspo"], r.get("nazwa"), pole,
                                             _tekst(bylo), _tekst(jest)))
            else:
                conn.execute("UPDATE placowki SET ostatni_import=? WHERE rspo=?",
                             (dzis, r["rspo"]))
                bez_zmian += 1

        # --- zniknięcia -----------------------------------------------------
        zniknelo, uwagi = 0, []
        w_pliku = {r["rspo"] for r in wiersze}
        if wykryj_znikniete:
            # Zakres liczymy ze stanu SPRZED importu, który mamy już w pamięci —
            # zapytanie do bazy per kandydat znaczyłoby przy pliku wojewódzkim
            # i ogólnopolskiej bazie 50 tysięcy zapytań na nic.
            kandydaci = [rspo for rspo, s in przed.items()
                         if rspo not in w_pliku and s.get("nieobecna_od") is None
                         and _w_zakresie(s, wojewodztwo)]
            baza_w_zakresie = sum(1 for s in przed.values()
                                  if _w_zakresie(s, wojewodztwo))
            if (baza_w_zakresie and len(kandydaci) > MIN_ZNIKNIEC
                    and len(kandydaci) > PROG_ZNIKNIEC * baza_w_zakresie):
                uwagi.append(
                    "Wstrzymano oznaczanie zniknięć: w pliku zabrakło %d z %d placówek "
                    "(%.0f%%). To wygląda na plik przefiltrowany w wyszukiwarce, "
                    "a nie na pełny wykaz — nic nie oznaczono."
                    % (len(kandydaci), baza_w_zakresie,
                       100.0 * len(kandydaci) / baza_w_zakresie))
            else:
                for rspo in kandydaci:
                    conn.execute("UPDATE placowki SET nieobecna_od=? WHERE rspo=?",
                                 (dzis, rspo))
                zniknelo = len(kandydaci)
        else:
            uwagi.append("Wykrywanie zniknięć wyłączone przy tym wgraniu.")

        if stat.get("powtorki_w_pliku"):
            uwagi.append("W pliku %d wierszy powtarzało numer RSPO — wzięliśmy "
                         "pierwsze wystąpienie." % stat["powtorki_w_pliku"])
        if stat.get("bez_numeru"):
            uwagi.append("%d wierszy bez numeru RSPO — pominięte (nie da się ich "
                         "zidentyfikować przy następnym wgraniu)." % stat["bez_numeru"])

        sekundy = round(time.time() - start, 1)
        cur = conn.execute("""
            INSERT INTO importy (kiedy, plik, rozmiar_mb, zakres, wierszy_w_pliku,
                                 w_zakresie, nowych, zmienionych, bez_zmian,
                                 zniknelo, wrocilo, sekundy, uwagi)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (db.teraz(), nazwa_pliku, plik_mod.rozmiar_mb(sciezka), zakres,
              stat["wierszy"], stat["w_zakresie"], len(nowe), len(zmienione),
              bez_zmian, zniknelo, wrocilo, sekundy, " ".join(uwagi) or None))
        import_id = cur.lastrowid
        for rspo, nazwa, pole, bylo, jest in dziennik:
            conn.execute("INSERT INTO zmiany (import_id, rspo, nazwa, pole, bylo, jest)"
                         " VALUES (?,?,?,?,?,?)", (import_id, rspo, nazwa, pole, bylo, jest))
        conn.commit()

        rejony.zasiej(conn)
        w_rejonach = rejony.przelicz(conn)

        return {
            "import_id": import_id,
            "plik": nazwa_pliku,
            "zakres": zakres,
            "wierszy_w_pliku": stat["wierszy"],
            "w_zakresie": stat["w_zakresie"],
            "nowych": len(nowe),
            "zmienionych": len(zmienione),
            "bez_zmian": bez_zmian,
            "zniknelo": zniknelo,
            "wrocilo": wrocilo,
            "w_rejonach": w_rejonach,
            "razem_w_bazie": conn.execute("SELECT COUNT(*) FROM placowki").fetchone()[0],
            "sekundy": sekundy,
            "uwagi": uwagi,
            "wg_typu": stat["wg_typu"].most_common(),
            "wg_powiatu": sorted(stat["wg_powiatu"].items(), key=lambda x: -x[1]),
            "zmiany": dziennik[:200],
        }
    finally:
        if wlasny:
            conn.close()


# ---------------------------------------------------------------------------

def _inne(a, b):
    """
    Czy wartość się zmieniła. `None` i pusty string to dla nas to samo — rejestr
    raz oddaje puste pole, raz spację, a dziennik zmian z wpisem
    „telefon: (puste) → (puste)” byłby szumem.
    """
    a = (a if a is not None else "")
    b = (b if b is not None else "")
    if isinstance(a, str):
        a = a.strip()
    if isinstance(b, str):
        b = b.strip()
    return a != b


def _tekst(v):
    return "" if v is None else str(v)


def _wstaw(conn, r, dzis):
    kolumny = db.KLUCZE_RSPO + ["pierwszy_import", "ostatni_import"]
    wartosci = [r.get(k) for k in db.KLUCZE_RSPO] + [dzis, dzis]
    conn.execute("INSERT INTO placowki (%s) VALUES (%s)"
                 % (", ".join(kolumny), ", ".join("?" * len(kolumny))), wartosci)


def _aktualizuj(conn, r, dzis, roznice, wyczysc_nieobecnosc=False):
    """
    Nadpisuje pola, które przyszły z rejestru. NIE dotyka `objeta`, `notatka`,
    `pierwszy_import` — to nasze kolumny i rejestr nie ma o nich pojęcia.
    """
    ustaw = ["%s=?" % k for k in db.KLUCZE_RSPO if k != "rspo"]
    wartosci = [r.get(k) for k in db.KLUCZE_RSPO if k != "rspo"]
    ustaw.append("ostatni_import=?")
    wartosci.append(dzis)
    if roznice:
        ustaw.append("ostatnia_zmiana=?")
        wartosci.append(dzis)
    if wyczysc_nieobecnosc:
        ustaw.append("nieobecna_od=NULL")
    wartosci.append(r["rspo"])
    conn.execute("UPDATE placowki SET %s WHERE rspo=?" % ", ".join(ustaw), wartosci)


def _w_zakresie(stan, wojewodztwo):
    """
    Czy placówka ze stanu sprzed importu leży w zakresie wgranego pliku.

    Bez tego wgranie pliku ze śląskiego oznaczyłoby jako „zniknięte” wszystko,
    co ktoś kiedyś wciągnął z innych województw.
    """
    if not wojewodztwo:
        return True
    return (stan.get("wojewodztwo") or "").upper() == wojewodztwo.upper()


def historia(conn, ile=20):
    return [dict(w) for w in conn.execute(
        "SELECT * FROM importy ORDER BY id DESC LIMIT ?", (ile,))]


def zmiany_importu(conn, import_id, ile=500):
    return [dict(w) for w in conn.execute(
        "SELECT * FROM zmiany WHERE import_id=? ORDER BY nazwa, pole LIMIT ?",
        (import_id, ile))]
