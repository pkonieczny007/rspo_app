# -*- coding: utf-8 -*-
"""
Odpytywanie bazy — lista placówek z filtrami i liczniki na pulpit.

Wszystkie filtry składamy w jednym miejscu, bo ten sam zestaw obsługuje trzy
rzeczy: listę na ekranie, licznik pod paskiem filtrów i eksport do XLSX.
Gdyby eksport budował warunki po swojemu, prędzej czy później oddałby inny
zbiór niż ten, który koordynatorka widzi na ekranie — a to jest ten rodzaj
błędu, którego nikt nie zauważa, dopóki nie jest za późno.
"""
import db

SORTOWANIA = {
    "nazwa":       "p.nazwa COLLATE NOCASE",
    "miejscowosc": "p.miejscowosc COLLATE NOCASE, p.nazwa COLLATE NOCASE",
    "uczniowie":   "COALESCE(p.liczba_uczniow,-1) DESC, p.nazwa COLLATE NOCASE",
    "typ":         "p.typ COLLATE NOCASE, p.nazwa COLLATE NOCASE",
    "rspo":        "p.rspo",
    "nowe":        "p.pierwszy_import DESC, p.nazwa COLLATE NOCASE",
}
SORT_DOMYSLNY = "nazwa"
NA_STRONIE = 100


def _warunki(f):
    """Buduje (lista_warunków, parametry) ze słownika filtrów."""
    war, par = [], []

    stan = f.get("stan") or "czynne"
    if stan == "czynne":
        war.append("p.nieobecna_od IS NULL")
    elif stan == "zniknely":
        war.append("p.nieobecna_od IS NOT NULL")

    q = (f.get("q") or "").strip()
    if q:
        # Szukamy po nazwie, miejscowości, ulicy i numerze RSPO naraz — bo
        # koordynatorka wpisuje w jedno pole to, co akurat ma pod ręką.
        war.append("(p.nazwa LIKE ? OR p.miejscowosc LIKE ? OR p.ulica LIKE ?"
                   " OR CAST(p.rspo AS TEXT) LIKE ? OR p.organ_nazwa LIKE ?)")
        par += ["%%%s%%" % q] * 5

    rejon = (f.get("rejon") or "").strip()
    if rejon == "brak":
        war.append("p.rspo NOT IN (SELECT rspo FROM placowka_rejon)")
    elif rejon == "dowolny":
        war.append("p.rspo IN (SELECT rspo FROM placowka_rejon)")
    elif rejon.isdigit():
        war.append("p.rspo IN (SELECT rspo FROM placowka_rejon WHERE rejon_id=?)")
        par.append(int(rejon))

    if f.get("powiat"):
        war.append("p.powiat = ?")
        par.append(f["powiat"])
    if f.get("gmina"):
        war.append("p.gmina = ?")
        par.append(f["gmina"])
    if f.get("typ"):
        war.append("p.typ = ?")
        par.append(f["typ"])
    if f.get("publicznosc"):
        war.append("p.publicznosc = ?")
        par.append(f["publicznosc"])
    if f.get("objeta") == "1":
        war.append("p.objeta = 1")
    elif f.get("objeta") == "0":
        war.append("p.objeta = 0")

    grupa = (f.get("grupa") or "").strip()
    if grupa == "nasze":
        war.append("(%s)" % _sql_grup(db.NASZE_GRUPY))
    elif grupa and grupa != "wszystkie":
        war.append("(%s)" % _sql_grup([grupa]))

    if f.get("uczniow_min"):
        try:
            war.append("COALESCE(p.liczba_uczniow,0) >= ?")
            par.append(int(f["uczniow_min"]))
        except (TypeError, ValueError):
            war.pop()

    return war, par


def _sql_grup(klucze):
    """
    Warunek SQL dla grup typów. Grupy rozpoznajemy po słowach kluczowych, więc
    warunek jest zbiorem LIKE-ów — ale z zastrzeżeniem: grupa wcześniejsza na
    liście „zabiera” swoje typy grupom późniejszym (patrz `db.grupa_typu`).
    Odtwarzamy tę samą kolejność, żeby ekran i eksport nie liczyły inaczej niż
    lista rejonów.
    """
    wzorce_grup = {k: w for k, _e, w in db.GRUPY_TYPOW}
    kolejnosc = [k for k, _e, _w in db.GRUPY_TYPOW]
    czesci = []
    for klucz in klucze:
        if klucz == "inne":
            wszystkie = [s for _k, _e, w in db.GRUPY_TYPOW for s in w]
            czesci.append("NOT (%s)" % " OR ".join(
                "lower(p.typ) LIKE '%%%s%%'" % s for s in wszystkie))
            continue
        wzorce = wzorce_grup.get(klucz)
        if not wzorce:
            continue
        moje = " OR ".join("lower(p.typ) LIKE '%%%s%%'" % s for s in wzorce)
        wczesniejsze = [s for k in kolejnosc[:kolejnosc.index(klucz)]
                        for s in wzorce_grup[k]]
        if wczesniejsze:
            blok = " OR ".join("lower(p.typ) LIKE '%%%s%%'" % s for s in wczesniejsze)
            czesci.append("((%s) AND NOT (%s))" % (moje, blok))
        else:
            czesci.append("(%s)" % moje)
    return " OR ".join(czesci) if czesci else "1=1"


def placowki(conn, f, strona=1, na_stronie=NA_STRONIE, wszystko=False):
    """Zwraca (wiersze, razem, podsumowanie)."""
    war, par = _warunki(f)
    gdzie = ("WHERE " + " AND ".join(war)) if war else ""

    razem = conn.execute("SELECT COUNT(*) FROM placowki p %s" % gdzie, par).fetchone()[0]
    pods = conn.execute("""
        SELECT COUNT(*) AS ile,
               COALESCE(SUM(p.liczba_uczniow),0) AS uczniow,
               SUM(CASE WHEN p.telefon IS NULL OR p.telefon='' THEN 1 ELSE 0 END) AS bez_telefonu,
               SUM(CASE WHEN p.email   IS NULL OR p.email=''   THEN 1 ELSE 0 END) AS bez_maila,
               SUM(CASE WHEN p.objeta=1 THEN 1 ELSE 0 END) AS objetych
          FROM placowki p %s""" % gdzie, par).fetchone()

    sort = SORTOWANIA.get(f.get("sort"), SORTOWANIA[SORT_DOMYSLNY])
    sql = """
        SELECT p.*, r.nazwa AS rejon_nazwa, r.kolor AS rejon_kolor, pr.przez AS rejon_przez
          FROM placowki p
          LEFT JOIN placowka_rejon pr ON pr.rspo = p.rspo
          LEFT JOIN rejony r ON r.id = pr.rejon_id
          %s ORDER BY %s""" % (gdzie, sort)
    if not wszystko:
        sql += " LIMIT ? OFFSET ?"
        par = par + [na_stronie, (max(1, strona) - 1) * na_stronie]
    wiersze = [dict(w) for w in conn.execute(sql, par)]
    for w in wiersze:
        w["grupa"] = db.grupa_typu(w["typ"])
        w["adres"] = _adres(w)
    return wiersze, razem, dict(pods)


def _adres(w):
    a = " ".join(x for x in (w.get("ulica") or "", w.get("nr_budynku") or "") if x).strip()
    if w.get("nr_lokalu"):
        a = (a + "/" + w["nr_lokalu"]).strip("/")
    return a


def oznacz_objete(conn, f, wartosc):
    """
    Ustawia flagę „objęta działaniem" na CAŁYM wyniku tych samych filtrów,
    które koordynatorka ma przed oczami. Zwraca liczbę ruszonych wierszy.

    Osobna funkcja, a nie warunki sklejane w `app.py`, bo to jedyny sposób,
    żeby zaznaczenie hurtem dotyczyło dokładnie tego, co pokazuje lista.
    """
    war, par = _warunki(f)
    gdzie = ("WHERE " + " AND ".join(war)) if war else ""
    cur = conn.execute(
        "UPDATE placowki SET objeta=? WHERE rspo IN (SELECT p.rspo FROM placowki p %s)"
        % gdzie, [1 if wartosc else 0] + par)
    conn.commit()
    return cur.rowcount


def wartosci_filtrow(conn):
    """Listy do rozwijanych filtrów — wyłącznie to, co realnie jest w bazie."""
    def kolumna(nazwa):
        return [w[0] for w in conn.execute(
            "SELECT DISTINCT %s FROM placowki WHERE %s IS NOT NULL AND %s<>''"
            " ORDER BY %s COLLATE NOCASE" % (nazwa, nazwa, nazwa, nazwa))]
    typy = [dict(w) for w in conn.execute("""
        SELECT typ, COUNT(*) AS ile FROM placowki
         WHERE nieobecna_od IS NULL GROUP BY typ ORDER BY ile DESC""")]
    return {
        "powiaty": kolumna("powiat"),
        "gminy": kolumna("gmina"),
        "typy": typy,
        "publicznosc": kolumna("publicznosc"),
    }


def pulpit(conn):
    """Liczby na stronę główną. Jedno zapytanie na kafelek, bo to tanie i czytelne."""
    def licz(sql, *par):
        return conn.execute(sql, par).fetchone()[0]

    razem = licz("SELECT COUNT(*) FROM placowki WHERE nieobecna_od IS NULL")
    w_rejonach = licz("""SELECT COUNT(*) FROM placowki p
                          JOIN placowka_rejon pr ON pr.rspo=p.rspo
                         WHERE p.nieobecna_od IS NULL""")
    nasze = licz("SELECT COUNT(*) FROM placowki p WHERE p.nieobecna_od IS NULL AND (%s)"
                 % _sql_grup(db.NASZE_GRUPY))
    wykaz = licz("""SELECT COUNT(*) FROM placowki p
                     JOIN placowka_rejon pr ON pr.rspo=p.rspo
                    WHERE p.nieobecna_od IS NULL AND (%s)""" % _sql_grup(db.NASZE_GRUPY))

    wg_grupy = {}
    for w in conn.execute("""SELECT p.typ, COUNT(*) n, COALESCE(SUM(p.liczba_uczniow),0) u
                               FROM placowki p JOIN placowka_rejon pr ON pr.rspo=p.rspo
                              WHERE p.nieobecna_od IS NULL GROUP BY p.typ"""):
        g = db.grupa_typu(w["typ"])
        poz = wg_grupy.setdefault(g, {"ile": 0, "uczniow": 0})
        poz["ile"] += w["n"]
        poz["uczniow"] += w["u"] or 0

    ostatni = conn.execute("SELECT * FROM importy ORDER BY id DESC LIMIT 1").fetchone()
    return {
        "razem": razem,
        "w_rejonach": w_rejonach,
        "poza_rejonami": razem - w_rejonach,
        "nasze_typy": nasze,
        "wykaz": wykaz,                    # rejony ∩ nasze typy — „tyle realnie obdzwonią”
        "znikniete": licz("SELECT COUNT(*) FROM placowki WHERE nieobecna_od IS NOT NULL"),
        "objete": licz("SELECT COUNT(*) FROM placowki WHERE objeta=1"),
        "uczniow": licz("""SELECT COALESCE(SUM(p.liczba_uczniow),0) FROM placowki p
                             JOIN placowka_rejon pr ON pr.rspo=p.rspo
                            WHERE p.nieobecna_od IS NULL"""),
        "wg_grupy": wg_grupy,
        "ostatni_import": dict(ostatni) if ostatni else None,
        "etykiety_grup": db.ETYKIETY_GRUP,
    }
