# -*- coding: utf-8 -*-
"""
Kopie zapasowe bazy RSPO.

PO CO TO W OGÓLE JEST, SKORO BAZĘ DA SIĘ ODTWORZYĆ Z PLIKU REJESTRU
Bo rejestr odtwarza tylko swoją część. Trzy kolumny są NASZE i nie ma ich
w żadnym pliku z rspo.gov.pl: `objeta` (na czym pracuje Kasia), `notatka`
i `pierwszy_import`. Do tego rejony — 17 startowych wraca samo, ale każde
poszerzenie terenu już nie. Wgranie pliku od nowa daje bazę, która wygląda
poprawnie i w której nie ma ani jednej decyzji klienta.

    python narzedzia/kopia.py zrob [--trzymaj 30]
    python narzedzia/kopia.py lista
    python narzedzia/kopia.py przywroc --z /data/kopie/rspo_2026-08-11_0600.db

DLACZEGO `sqlite3.backup`, A NIE `cp`
Zwykłe skopiowanie pliku działającej bazy potrafi złapać stan w połowie zapisu
— plik ma poprawną nazwę i rozmiar, a nie daje się otworzyć. Wyjdzie to na jaw
dopiero w dniu, w którym kopia jest potrzebna. API `backup` czyta bazę pod
blokadą i jest na to odporne; przy okazji zwija WAL, więc kopia to JEDEN plik,
bez towarzyszących `-wal` i `-shm`.
"""
import argparse
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # konsola Windows to cp1250

import db  # noqa: E402

KATALOG = os.path.join(db.DATA_DIR, "kopie")


def zrob(trzymaj=30):
    os.makedirs(KATALOG, exist_ok=True)
    nazwa = "rspo_%s.db" % time.strftime("%Y-%m-%d_%H%M")
    cel = os.path.join(KATALOG, nazwa)

    zrodlo = sqlite3.connect(db.DB_PATH, timeout=30)
    kopia = sqlite3.connect(cel)
    try:
        zrodlo.backup(kopia)
    finally:
        kopia.close()
        zrodlo.close()

    ile = _policz(cel)
    print("kopia: %s  (%.1f MB, %d placówek)"
          % (cel, os.path.getsize(cel) / 1048576.0, ile))
    if trzymaj:
        _sprzataj(trzymaj)
    return cel


def _policz(sciezka):
    """
    Kopia jest kopią dopiero wtedy, gdy da się z niej policzyć rekordy.

    Sam fakt, że plik powstał i ma sensowny rozmiar, nie znaczy nic — dlatego
    liczymy placówki od razu po zapisie, a nie „kiedyś przy odtwarzaniu”.
    """
    conn = sqlite3.connect(sciezka)
    try:
        return conn.execute("SELECT COUNT(*) FROM placowki").fetchone()[0]
    finally:
        conn.close()


def _sprzataj(dni):
    """
    Kasuje kopie starsze niż `dni`, ZOSTAWIAJĄC poniedziałkowe.

    Po co wyjątek na poniedziałki: awarię z zeszłego tygodnia zauważa się
    następnego dnia, a błąd w danych sprzed dwóch miesięcy — dopiero gdy ktoś
    porówna wykaz. Poniedziałki dają rzadką, ale długą pamięć bez trzymania
    wszystkiego.
    """
    granica = time.time() - dni * 86400
    for plik in sorted(os.listdir(KATALOG)):
        if not plik.endswith(".db"):
            continue
        pelna = os.path.join(KATALOG, plik)
        stat = os.stat(pelna)
        if stat.st_mtime >= granica:
            continue
        if time.localtime(stat.st_mtime).tm_wday == 0:
            continue
        os.remove(pelna)
        print("usunięto starą kopię: %s" % plik)


def lista():
    if not os.path.isdir(KATALOG):
        print("Nie ma jeszcze żadnej kopii (%s)." % KATALOG)
        return
    pliki = sorted(p for p in os.listdir(KATALOG) if p.endswith(".db"))
    if not pliki:
        print("Nie ma jeszcze żadnej kopii (%s)." % KATALOG)
        return
    for p in pliki:
        pelna = os.path.join(KATALOG, p)
        print("%-32s %7.1f MB  %s" % (
            p, os.path.getsize(pelna) / 1048576.0,
            time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(pelna)))))
    print("\nrazem: %d kopii w %s" % (len(pliki), KATALOG))


def przywroc(skad):
    if not os.path.isfile(skad):
        print("BŁĄD: nie ma pliku %s" % skad)
        return 1
    ile = _policz(skad)   # nie podmieniaj bazy plikiem, którego nie dało się otworzyć

    # Zanim cokolwiek nadpiszemy — kopia stanu bieżącego. Odtwarzanie robi się
    # w pośpiechu i zwykle nie tego pliku, co trzeba.
    if os.path.isfile(db.DB_PATH):
        zrob(trzymaj=0)

    # Katalog bazy może nie istnieć — odtwarzamy przecież także na czystej
    # maszynie, gdzie aplikacja nie zdążyła się jeszcze ani razu uruchomić.
    os.makedirs(os.path.dirname(db.DB_PATH), exist_ok=True)
    zrodlo = sqlite3.connect(skad)
    cel = sqlite3.connect(db.DB_PATH, timeout=30)
    try:
        zrodlo.backup(cel)
    finally:
        cel.close()
        zrodlo.close()
    # WAL i SHM zostały po POPRZEDNIEJ bazie i opisują nieistniejące już strony.
    for ogon in ("-wal", "-shm"):
        try:
            os.remove(db.DB_PATH + ogon)
        except OSError:
            pass
    print("przywrócono %s → %s (%d placówek)" % (skad, db.DB_PATH, ile))
    return 0


def main():
    p = argparse.ArgumentParser(description="Kopie zapasowe bazy RSPO")
    pod = p.add_subparsers(dest="co", required=True)

    z = pod.add_parser("zrob", help="zrób kopię")
    z.add_argument("--trzymaj", type=int, default=30,
                   help="usuń kopie starsze niż tyle dni (0 = nic nie kasuj)")

    pod.add_parser("lista", help="pokaż, co jest")

    pr = pod.add_parser("przywroc", help="wgraj kopię na miejsce bazy")
    pr.add_argument("--z", dest="skad", required=True)

    a = p.parse_args()
    if a.co == "zrob":
        zrob(a.trzymaj)
    elif a.co == "lista":
        lista()
    else:
        return przywroc(a.skad)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
