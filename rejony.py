# -*- coding: utf-8 -*-
"""
Rejony działania — i ich poszerzanie.

CO TO JEST REJON
Obszar, po którym jeździ trener. Nie jest to ani powiat, ani miasto — to zbiór
jednego i drugiego. „Knurów” to jedna gmina wyjęta z powiatu gliwickiego,
„pszczyński” to cały powiat z kilkunastoma wsiami. Dlatego rejon nie jest
kolumną na placówce, tylko LISTĄ OBSZARÓW: dopisanie gminy do rejonu ma być
jedną linijką i natychmiastowym przeliczeniem, a nie przepisywaniem tysiąca
wierszy.

PIERWSZEŃSTWO: GMINA BIJE POWIAT
Gdy powiat gliwicki wpadnie kiedyś w całości do rejonu „Gliwice”, a gmina
Knurów jest już osobnym rejonem — Knurów zostaje przy swoim. Reguła
„bardziej szczegółowy obszar wygrywa” jest jedyną, której nie trzeba pamiętać.

DLACZEGO PRZELICZAMY DO TABELI, A NIE LICZYMY W LOCIE
`placowka_rejon` to tabela pomocnicza odbudowywana po każdej zmianie. Zapytanie
liczące rejon w locie musiałoby przy każdym odświeżeniu ekranu robić JOIN
z pierwszeństwem gminy nad powiatem — działa, ale jest nieczytelne i wraca
w każdym miejscu, gdzie potrzeba licznika. Przeliczenie 6 tysięcy wierszy trwa
ułamek sekundy, więc płacimy raz zamiast przy każdym kliknięciu.
"""
import db

# ---------------------------------------------------------------------------
# REJONY STARTOWE — lista od Kasi z 08.08.2026.
#
# W rejestrze „powiat” dla miasta na prawach powiatu ma nazwę miasta
# („Katowice”), a dla powiatu ziemskiego jest z małej litery („mikołowski”).
# Nazwy rejonów piszemy tak, jak mówi o nich klient.
#
# Kolory: paleta narzędzia, żeby rejon miał stały kolor na liście, w raporcie
# i — kiedyś — na mapie. Zmiana koloru to zmiana jednej linijki.
# ---------------------------------------------------------------------------

REJONY_STARTOWE = [
    # (nazwa rejonu, kolor, [(rodzaj, wartość), ...])
    ("Katowice",              "#1c9dc4", [("powiat", "Katowice")]),
    ("Sosnowiec",             "#22c2f2", [("powiat", "Sosnowiec")]),
    ("Zabrze",                "#0b6f93", [("powiat", "Zabrze")]),
    ("Rybnik",                "#2e8b9e", [("powiat", "Rybnik")]),
    ("Tychy",                 "#3aa6a0", [("powiat", "Tychy")]),
    ("Dąbrowa Górnicza",      "#4f8fc4", [("powiat", "Dąbrowa Górnicza")]),
    ("Ruda Śląska",           "#6a7fc0", [("powiat", "Ruda Śląska")]),
    ("Chorzów",               "#8a6fb8", [("powiat", "Chorzów")]),
    ("Jaworzno",              "#a86ea6", [("powiat", "Jaworzno")]),
    ("Żory",                  "#c26f92", [("powiat", "Żory")]),
    ("Siemianowice Śląskie",  "#d1766f", [("powiat", "Siemianowice Śląskie")]),
    ("Piekary Śląskie",       "#d68a29", [("powiat", "Piekary Śląskie")]),
    ("Świętochłowice",        "#c99a2e", [("powiat", "Świętochłowice")]),
    ("powiat pszczyński",     "#7a9a3c", [("powiat", "pszczyński")]),
    ("powiat będziński",      "#5f9455", [("powiat", "będziński")]),
    ("powiat mikołowski",     "#3f8f6b", [("powiat", "mikołowski")]),
    # Kasia: „Knurów” — jedna gmina z powiatu gliwickiego, reszty powiatu nie bierzemy.
    ("Knurów",                "#8a6516", [("gmina", "Knurów")]),
]

# Miasta, które klient ma w swoim słowniku rejonów w aplikacji leadów, ale których
# nasza lista nie obejmuje. Nie jest to propozycja ekspansji — to poprawka
# konfiguracji: klient sam je sobie wpisał, a wykaz z rejestru je pomijał.
# Podpowiadamy je na ekranie rejonów, żeby ktoś o nich pamiętał.
SUGEROWANE = {
    "Gliwice":         "klient ma ten rejon w swoim słowniku; przylega do Knurowa i Zabrza",
    "Bytom":           "klient ma ten rejon w swoim słowniku; dziura między Zabrzem, Piekarami i Rudą",
    "Mysłowice":       "klient ma ten rejon w swoim słowniku; między Katowicami, Sosnowcem i Jaworznem",
    "tarnogórski":     "klient ma w słowniku Tarnowskie Góry; powiat przylega do Piekar i Bytomia",
    "gliwicki":        "reszta powiatu wokół Knurowa, który już obsługujemy",
    "lubliniecki":     "rejon dalszy — osobny teren",
    "wodzisławski":    "przylega do Rybnika i Żor",
    "raciborski":      "rejon dalszy — osobny teren",
    "bieruńsko-lędziński": "przylega do Tychów i Jaworzna",
    "zawierciański":   "przylega do powiatu będzińskiego",
    "gliwicki (reszta)": "",
}


def zasiej(conn):
    """
    Zakłada rejony startowe, jeśli tabela jest pusta.

    Świadomie NIE dopisuje ich do bazy, w której ktoś już rejony poustawiał —
    inaczej po każdym restarcie wracałyby skasowane obszary i nikt by nie
    zrozumiał, dlaczego „Gliwice same się dodały”.
    """
    if conn.execute("SELECT COUNT(*) FROM rejony").fetchone()[0]:
        return 0
    for i, (nazwa, kolor, obszary) in enumerate(REJONY_STARTOWE):
        cur = conn.execute(
            "INSERT INTO rejony (nazwa, kolor, kolejnosc) VALUES (?,?,?)",
            (nazwa, kolor, i))
        for rodzaj, wartosc in obszary:
            conn.execute(
                "INSERT OR IGNORE INTO rejon_obszary (rejon_id, rodzaj, wartosc)"
                " VALUES (?,?,?)", (cur.lastrowid, rodzaj, wartosc))
    conn.commit()
    return len(REJONY_STARTOWE)


def przelicz(conn):
    """
    Odbudowuje `placowka_rejon`. Wywoływane po imporcie i po każdej zmianie rejonów.

    Kolejność INSERT-ów niesie regułę pierwszeństwa: najpierw powiaty, potem
    gminy z `INSERT OR REPLACE` — więc gmina nadpisuje przypisanie po powiecie.
    To jedno miejsce, w którym ta reguła żyje.
    """
    conn.execute("DELETE FROM placowka_rejon")
    for rodzaj in ("powiat", "gmina"):
        conn.execute("""
            INSERT OR REPLACE INTO placowka_rejon (rspo, rejon_id, przez)
            SELECT p.rspo, o.rejon_id, ? || ':' || o.wartosc
              FROM placowki p
              JOIN rejon_obszary o
                ON o.rodzaj = ?
               AND lower(o.wartosc) = lower(p.%s)
        """ % rodzaj, (rodzaj, rodzaj))
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM placowka_rejon").fetchone()[0]


def lista(conn):
    """Rejony z licznikami — do ekranu rejonów i do list rozwijanych."""
    wiersze = conn.execute("""
        SELECT r.id, r.nazwa, r.kolor, r.opis, r.kolejnosc,
               COUNT(pr.rspo) AS placowek
          FROM rejony r
          LEFT JOIN placowka_rejon pr ON pr.rejon_id = r.id
         GROUP BY r.id
         ORDER BY r.kolejnosc, r.nazwa
    """).fetchall()
    out = []
    for w in wiersze:
        r = dict(w)
        r["obszary"] = [dict(o) for o in conn.execute(
            "SELECT id, rodzaj, wartosc FROM rejon_obszary WHERE rejon_id=?"
            " ORDER BY rodzaj DESC, wartosc", (w["id"],))]
        r["wg_grupy"] = _wg_grupy(conn, w["id"])
        out.append(r)
    return out


def _wg_grupy(conn, rejon_id):
    """Rozbicie rejonu na grupy typów — „ile tu podstawówek, ile przedszkoli”."""
    licz = {}
    for w in conn.execute("""
        SELECT p.typ, COUNT(*) AS n
          FROM placowki p JOIN placowka_rejon pr ON pr.rspo = p.rspo
         WHERE pr.rejon_id = ? AND p.nieobecna_od IS NULL
         GROUP BY p.typ
    """, (rejon_id,)):
        g = db.grupa_typu(w["typ"])
        licz[g] = licz.get(g, 0) + w["n"]
    return licz


def obszary_wolne(conn, tylko_nasze_typy=True):
    """
    Powiaty, które są w bazie, a nie należą do żadnego rejonu — „białe plamy”.

    To jest odpowiedź na „możemy sprawdzać i poszerzać rejony”: lista posortowana
    po tym, ile placówek by doszło, z podpowiedzią przy tych, które klient ma
    już w swoim słowniku, a nasza konfiguracja ich nie obejmuje.
    """
    warunek_typu = ""
    if tylko_nasze_typy:
        warunek_typu = " AND (%s)" % _sql_nasze_typy()
    wiersze = conn.execute("""
        SELECT p.powiat,
               COUNT(*) AS placowek,
               SUM(CASE WHEN lower(p.typ) LIKE '%%szkoła podstawowa%%' THEN 1 ELSE 0 END) AS podstawowek,
               SUM(CASE WHEN lower(p.typ) LIKE '%%przedszkol%%' THEN 1 ELSE 0 END) AS przedszkoli,
               COALESCE(SUM(p.liczba_uczniow),0) AS uczniow
          FROM placowki p
         WHERE p.nieobecna_od IS NULL
           AND p.powiat IS NOT NULL
           AND p.rspo NOT IN (SELECT rspo FROM placowka_rejon)
           %s
         GROUP BY p.powiat
         ORDER BY placowek DESC
    """ % warunek_typu).fetchall()
    out = []
    for w in wiersze:
        r = dict(w)
        r["podpowiedz"] = SUGEROWANE.get(w["powiat"], "")
        out.append(r)
    # Najpierw to, o czym wiadomo, że powinno nas obchodzić (klient ma ten rejon
    # w swoim słowniku albo teren przylega do naszego), potem reszta wg wielkości.
    # Samo sortowanie po liczbie placówek wypchnęłoby na górę Częstochowę
    # i powiat żywiecki — duże, ale po drugiej stronie województwa.
    out.sort(key=lambda r: (not r["podpowiedz"], -r["placowek"]))
    return out


def _sql_nasze_typy():
    """Warunek SQL „to jest typ, w którym prowadzimy zajęcia”."""
    slowa = []
    for klucz, _et, wzorce in db.GRUPY_TYPOW:
        if klucz in db.NASZE_GRUPY:
            slowa += list(wzorce)
    return " OR ".join("lower(p.typ) LIKE '%%%s%%'" % s for s in slowa)


def podglad_obszaru(conn, rodzaj, wartosc):
    """Ile placówek doszłoby po dopisaniu tego obszaru — liczba PRZED zapisem."""
    kol = "powiat" if rodzaj == "powiat" else "gmina"
    w = conn.execute("""
        SELECT COUNT(*) AS wszystkie,
               SUM(CASE WHEN %s THEN 1 ELSE 0 END) AS nasze_typy,
               COALESCE(SUM(p.liczba_uczniow),0) AS uczniow
          FROM placowki p
         WHERE lower(p.%s) = lower(?) AND p.nieobecna_od IS NULL
    """ % (_sql_nasze_typy(), kol), (wartosc,)).fetchone()
    return dict(w)


def dodaj_obszar(conn, rejon_id, rodzaj, wartosc):
    """
    Dopisuje obszar do rejonu. Zwraca (ok, komunikat).

    Obszar zajęty przez inny rejon PRZENOSIMY, ale mówimy o tym wprost — cicha
    zamiana zmieniłaby liczby w dwóch rejonach naraz i nikt by nie skojarzył
    dlaczego.
    """
    if rodzaj not in ("powiat", "gmina"):
        return False, "Nieznany rodzaj obszaru: %s" % rodzaj
    wartosc = (wartosc or "").strip()
    if not wartosc:
        return False, "Pusta nazwa obszaru"

    stary = conn.execute(
        "SELECT o.id, r.nazwa FROM rejon_obszary o JOIN rejony r ON r.id=o.rejon_id"
        " WHERE o.rodzaj=? AND lower(o.wartosc)=lower(?)", (rodzaj, wartosc)).fetchone()
    if stary:
        conn.execute("UPDATE rejon_obszary SET rejon_id=? WHERE id=?",
                     (rejon_id, stary["id"]))
        conn.commit()
        przelicz(conn)
        return True, "%s „%s” przeniesiony z rejonu „%s”" % (
            rodzaj.capitalize(), wartosc, stary["nazwa"])

    conn.execute("INSERT INTO rejon_obszary (rejon_id, rodzaj, wartosc) VALUES (?,?,?)",
                 (rejon_id, rodzaj, wartosc))
    conn.commit()
    ile = przelicz(conn)
    return True, "Dodano %s „%s”. Placówek w rejonach: %d" % (rodzaj, wartosc, ile)


def usun_obszar(conn, obszar_id):
    w = conn.execute("SELECT rodzaj, wartosc FROM rejon_obszary WHERE id=?",
                     (obszar_id,)).fetchone()
    if not w:
        return False, "Nie ma takiego obszaru"
    conn.execute("DELETE FROM rejon_obszary WHERE id=?", (obszar_id,))
    conn.commit()
    przelicz(conn)
    return True, "Usunięto %s „%s” z rejonu" % (w["rodzaj"], w["wartosc"])


def nowy_rejon(conn, nazwa, kolor=None, obszary=()):
    """Nowy rejon + od razu jego obszary — „poszerzenie o Gliwice” w jednym ruchu."""
    nazwa = (nazwa or "").strip()
    if not nazwa:
        return None, "Rejon musi mieć nazwę"
    if conn.execute("SELECT 1 FROM rejony WHERE lower(nazwa)=lower(?)", (nazwa,)).fetchone():
        return None, "Rejon „%s” już istnieje" % nazwa
    maks = conn.execute("SELECT COALESCE(MAX(kolejnosc),0)+1 FROM rejony").fetchone()[0]
    cur = conn.execute("INSERT INTO rejony (nazwa, kolor, kolejnosc) VALUES (?,?,?)",
                       (nazwa, kolor or "#667085", maks))
    rejon_id = cur.lastrowid
    for rodzaj, wartosc in obszary:
        conn.execute("INSERT OR REPLACE INTO rejon_obszary (rejon_id, rodzaj, wartosc)"
                     " VALUES (?,?,?)", (rejon_id, rodzaj, wartosc))
    conn.commit()
    przelicz(conn)
    return rejon_id, "Dodano rejon „%s”" % nazwa


def usun_rejon(conn, rejon_id):
    w = conn.execute("SELECT nazwa FROM rejony WHERE id=?", (rejon_id,)).fetchone()
    if not w:
        return False, "Nie ma takiego rejonu"
    conn.execute("DELETE FROM rejony WHERE id=?", (rejon_id,))
    conn.commit()
    przelicz(conn)
    return True, "Usunięto rejon „%s” (placówki zostają w bazie, tracą tylko przypisanie)" % w["nazwa"]


def gminy_powiatu(conn, powiat):
    """Gminy danego powiatu z liczbą placówek — do poszerzania rejonu o jedną gminę."""
    return [dict(w) for w in conn.execute("""
        SELECT gmina, COUNT(*) AS placowek
          FROM placowki
         WHERE lower(powiat)=lower(?) AND nieobecna_od IS NULL AND gmina IS NOT NULL
         GROUP BY gmina ORDER BY gmina
    """, (powiat,))]
