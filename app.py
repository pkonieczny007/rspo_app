# -*- coding: utf-8 -*-
"""
RSPO — narzędzie do zarządzania bazą placówek oświatowych.

PO CO OSOBNA APLIKACJA, A NIE EKRAN W `leady_app_v5`
Bo to inna praca i inny rytm. Aplikacja leadów obsługuje codzienną sprzedaż —
handlowiec w terenie, koordynatorka rozdająca szkoły. Tutaj raz na miesiąc
ktoś wgrywa plik z rejestru, ogląda, co się zmieniło, i decyduje, czy poszerzyć
teren. Trzymanie tego osobno znaczy, że wgranie 42-megabajtowego pliku i próba
z nowym rejonem nie mogą niczego zepsuć w bazie, na której pracują handlowcy.

Połączenie obu jest przewidziane i nie wymaga integracji: ekran „Wykaz” oddaje
plik XLSX w formacie, który aplikacja leadów łyka przez „↑ Import → źródło
RSPO”. Gdy narzędzie się sprawdzi, wchodzi do aplikacji jako ekran koordynatora
— i wtedy zamiast pliku będzie wspólna baza.

EKRANY
  /            pulpit — ile mamy, ile w rejonach, co ostatnio doszło
  /placowki    lista z filtrami (rejon, typ, powiat, gmina, publiczność, szukajka)
  /rejony      rejony działania, ich obszary i „białe plamy” do poszerzenia
  /import      wgranie pliku z rspo.gov.pl + raport zmian + historia
  /eksport     XLSX z tego, co widać po filtrach
"""
import os
import time

from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   send_file, url_for)

import db
import eksport
import magazyn
import plik as plik_mod
import rejony
import zapytania

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rspo-narzedzie")

# Plik z całej Polski waży 42 MB. Domyślny limit Flaska (brak) przepuściłby go,
# ale wolimy mieć jawny sufit niż przyjmować cokolwiek — 250 MB to zapas na
# wypadek, gdyby rejestr rozrósł eksport albo ktoś wgrał go jako .xlsx.
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024

KATALOG_WGRANE = os.path.join(db.DATA_DIR, "wgrane")

PORT_DOMYSLNY = "5310"     # 5301 zajmuje aplikacja leadów

# Wyszukiwarka rejestru — stąd bierze się plik. Adres trzymamy w jednym miejscu,
# bo prowadzi do niego kilka ekranów, a strony rządowe potrafią przenieść
# wyszukiwarkę pod inny adres i wtedy poprawia się jedną linijkę.
RSPO_WWW = "https://rspo.gov.pl/institutions"


# --------------------------------------------------------------------- wspólne

@app.context_processor
def wspolne():
    return {
        "grupy_typow": db.GRUPY_TYPOW,
        "etykiety_grup": db.ETYKIETY_GRUP,
        "nasze_grupy": db.NASZE_GRUPY,
        "rspo_www": RSPO_WWW,
        "dzis": db.dzis(),
    }


@app.template_filter("liczba")
def _liczba(v):
    """1573 → „1 573”. Wąska spacja rozdziela tysiące — łatwiej porównać wzrokiem."""
    try:
        return "{:,}".format(int(v)).replace(",", " ")
    except (TypeError, ValueError):
        return v


def filtry_z_zapytania():
    """
    Filtry czytamy z adresu, nie z sesji.

    Po co: adres z filtrami da się wysłać mailem („zobacz te 96 placówek
    w Bytomiu”) i da się do niego wrócić przyciskiem wstecz. Filtr schowany
    w sesji wygląda jak brakujące dane — nikt nie wie, dlaczego widzi 300
    zamiast 6000.
    """
    return {k: (request.args.get(k) or "").strip() for k in
            ("q", "rejon", "powiat", "gmina", "typ", "grupa", "publicznosc",
             "objeta", "stan", "sort", "uczniow_min")}


@app.template_global()
def link(endpoint=None, **zmiany):
    """
    Adres z BIEŻĄCYMI filtrami i podmienioną jedną rzeczą.

    Bez tego kliknięcie w nagłówek kolumny albo w przełącznik rodzaju gubiłoby
    wybrany rejon — a nikt by nie zauważył, że lista przestała być tą, którą
    przed chwilą oglądał. Puste wartości wypadają z adresu, żeby dało się go
    wkleić w maila bez ogona pustych parametrów.
    """
    args = {k: v for k, v in filtry_z_zapytania().items() if v}
    args.update(zmiany)
    return url_for(endpoint or request.endpoint,
                   **{k: v for k, v in args.items() if v not in ("", None)})


def _polaczenie():
    conn = db.polacz()
    return conn


# --------------------------------------------------------------------- pulpit

@app.route("/")
def pulpit():
    conn = _polaczenie()
    try:
        dane = zapytania.pulpit(conn)
        r = rejony.lista(conn)
        return render_template("pulpit.html", d=dane, rejony=r,
                               historia=magazyn.historia(conn, 5), nav="pulpit")
    finally:
        conn.close()


# ------------------------------------------------------------------- placówki

@app.route("/placowki")
def placowki():
    conn = _polaczenie()
    try:
        f = filtry_z_zapytania()
        strona = max(1, int(request.args.get("strona") or 1))
        wiersze, razem, pods = zapytania.placowki(conn, f, strona=strona)
        return render_template(
            "placowki.html", wiersze=wiersze, razem=razem, pods=pods, f=f,
            strona=strona, na_stronie=zapytania.NA_STRONIE,
            stron=max(1, (razem + zapytania.NA_STRONIE - 1) // zapytania.NA_STRONIE),
            slowniki=zapytania.wartosci_filtrow(conn),
            rejony=rejony.lista(conn), nav="placowki")
    finally:
        conn.close()


@app.route("/placowka/<int:rspo>")
def placowka(rspo):
    conn = _polaczenie()
    try:
        w = conn.execute("""
            SELECT p.*, r.nazwa AS rejon_nazwa, r.kolor AS rejon_kolor
              FROM placowki p
              LEFT JOIN placowka_rejon pr ON pr.rspo=p.rspo
              LEFT JOIN rejony r ON r.id=pr.rejon_id
             WHERE p.rspo=?""", (rspo,)).fetchone()
        if not w:
            flash("Nie ma w bazie placówki o numerze RSPO %s" % rspo, "err")
            return redirect(url_for("placowki"))
        rodzina = _rodzina_zespolu(conn, dict(w))
        zmiany = [dict(x) for x in conn.execute(
            "SELECT z.*, i.kiedy FROM zmiany z JOIN importy i ON i.id=z.import_id"
            " WHERE z.rspo=? ORDER BY z.id DESC LIMIT 50", (rspo,))]
        return render_template("placowka.html", p=dict(w), rodzina=rodzina,
                               zmiany=zmiany, pola=db.POLA_RSPO,
                               etykiety=db.ETYKIETY, nav="placowki")
    finally:
        conn.close()


def _rodzina_zespolu(conn, p):
    """
    Pozostałe człony tego samego zespołu szkół.

    Po co: w naszych rejonach 278 rekordów to zespoły, a 341 to ich składowe —
    ten sam adres i ten sam telefon w dwóch albo trzech wierszach. Bez tego
    handlowiec dzwoni pod ten sam numer kilka razy, za każdym razem przekonany,
    że dzwoni gdzie indziej. Rejestr wiąże je kolumną „RSPO podmiotu
    nadrzędnego” i to jedyne, czego do tego potrzeba.
    """
    rodzic = (p.get("rspo_nadrzedny") or "").strip()
    numery, out = set(), []

    def dolacz(sql, par):
        for x in conn.execute(sql, par):
            if x["rspo"] != p["rspo"] and x["rspo"] not in numery:
                numery.add(x["rspo"])
                out.append(dict(x))

    kolumny = "rspo, nazwa, typ, telefon, miejscowosc"
    # moje składowe
    dolacz("SELECT %s FROM placowki WHERE rspo_nadrzedny=? LIMIT 40" % kolumny,
           (str(p["rspo"]),))
    if rodzic:
        # mój zespół i jego pozostałe człony
        dolacz("SELECT %s FROM placowki WHERE rspo=?" % kolumny, (rodzic,))
        dolacz("SELECT %s FROM placowki WHERE rspo_nadrzedny=? LIMIT 40" % kolumny,
               (rodzic,))
    return out


@app.post("/api/objeta")
def api_objeta():
    """Przełącznik „objęta działaniem” na jednej placówce."""
    dane = request.get_json(silent=True) or {}
    conn = _polaczenie()
    try:
        conn.execute("UPDATE placowki SET objeta=? WHERE rspo=?",
                     (1 if dane.get("wartosc") else 0, int(dane.get("rspo"))))
        conn.commit()
        return jsonify(ok=True)
    except (TypeError, ValueError):
        return jsonify(ok=False, blad="zły numer RSPO"), 400
    finally:
        conn.close()


@app.post("/placowki/objete")
def objete_hurtem():
    """
    „Oznacz wszystkie z tych filtrów jako objęte działaniem”.

    Po co hurtem: flaga ma sens dopiero na tysiącu placówek, a klikanie tysiąca
    przełączników to nie jest praca dla człowieka. Działa na dokładnie tym
    zbiorze, który koordynatorka ma przed oczami — te same filtry, ten sam SQL.
    """
    f = {k: (request.form.get(k) or "").strip() for k in
         ("q", "rejon", "powiat", "gmina", "typ", "grupa", "publicznosc",
          "objeta", "stan", "uczniow_min")}
    wartosc = 1 if request.form.get("wartosc") == "1" else 0
    conn = _polaczenie()
    try:
        ile = zapytania.oznacz_objete(conn, f, wartosc)
        flash("%s %d placówek." % ("Oznaczono jako objęte działaniem:" if wartosc
                                   else "Zdjęto oznaczenie z", ile), "ok")
    finally:
        conn.close()
    return redirect(request.referrer or url_for("placowki"))


# --------------------------------------------------------------------- rejony

@app.route("/rejony")
def rejony_view():
    conn = _polaczenie()
    try:
        rejony.zasiej(conn)
        return render_template(
            "rejony.html",
            rejony=rejony.lista(conn),
            wolne=rejony.obszary_wolne(conn),
            wolne_wszystko=rejony.obszary_wolne(conn, tylko_nasze_typy=False),
            nav="rejony")
    finally:
        conn.close()


@app.post("/rejony/obszar")
def rejon_obszar():
    """
    Jedno wejście na trzy ruchy: dodaj obszar / usuń obszar / załóż rejon.

    Brakujące pole kończy się komunikatem, nie stroną błędu — formularz na
    ekranie rejonów ma kilka wariantów i pomyłka w jednym z nich nie może
    wyglądać jak awaria narzędzia.
    """
    conn = _polaczenie()
    try:
        akcja = request.form.get("akcja")
        rodzaj = request.form.get("rodzaj") or "powiat"
        wartosc = (request.form.get("wartosc") or "").strip()
        if akcja == "usun":
            ok, kom = rejony.usun_obszar(conn, _int(request.form.get("obszar_id")))
        elif akcja == "nowy-rejon":
            nazwa = (request.form.get("nazwa") or wartosc).strip()
            _id, kom = rejony.nowy_rejon(conn, nazwa, request.form.get("kolor"),
                                         [(rodzaj, wartosc)] if wartosc else [])
            ok = _id is not None
        elif not request.form.get("rejon_id"):
            ok, kom = False, "Nie wiadomo, do którego rejonu dopisać — brak pola rejon_id."
        else:
            ok, kom = rejony.dodaj_obszar(conn, _int(request.form["rejon_id"]),
                                          rodzaj, wartosc)
        flash(kom, "ok" if ok else "err")
    finally:
        conn.close()
    return redirect(url_for("rejony_view"))


def _int(v, domyslnie=0):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return domyslnie


@app.post("/rejony/usun/<int:rejon_id>")
def rejon_usun(rejon_id):
    conn = _polaczenie()
    try:
        ok, kom = rejony.usun_rejon(conn, rejon_id)
        flash(kom, "ok" if ok else "err")
    finally:
        conn.close()
    return redirect(url_for("rejony_view"))


@app.get("/api/podglad-obszaru")
def api_podglad():
    """Ile placówek doszłoby — liczba PRZED kliknięciem „Dodaj”."""
    conn = _polaczenie()
    try:
        d = rejony.podglad_obszaru(conn, request.args.get("rodzaj", "powiat"),
                                   request.args.get("wartosc", ""))
        return jsonify(**d)
    finally:
        conn.close()


@app.get("/api/gminy")
def api_gminy():
    conn = _polaczenie()
    try:
        return jsonify(gminy=rejony.gminy_powiatu(conn, request.args.get("powiat", "")))
    finally:
        conn.close()


# --------------------------------------------------------------------- import

@app.route("/import", methods=["GET", "POST"])
def import_view():
    conn = _polaczenie()
    try:
        raport = None
        if request.method == "POST":
            raport = _obsluz_wgranie(conn)
        return render_template("import.html", raport=raport,
                               historia=magazyn.historia(conn, 20), nav="import")
    finally:
        conn.close()


def _obsluz_wgranie(conn):
    f = request.files.get("plik")
    if not f or not f.filename:
        flash("Nie wybrano pliku.", "err")
        return None
    if not f.filename.lower().endswith((".csv", ".xlsx", ".xlsm")):
        flash("Oczekuję pliku .csv (pobranego z rspo.gov.pl) albo .xlsx.", "err")
        return None

    os.makedirs(KATALOG_WGRANE, exist_ok=True)
    # Wgrany plik zostaje na dysku pod nazwą ze znacznikiem czasu. Po co: gdy
    # raport pokaże coś dziwnego, chcemy móc wrócić do TEGO pliku, a nie do
    # „chyba tego, co wtedy pobierałem”.
    bezpieczna = "".join(c for c in os.path.basename(f.filename)
                         if c.isalnum() or c in "._- ").strip() or "rspo.csv"
    sciezka = os.path.join(KATALOG_WGRANE,
                           "%s_%s" % (time.strftime("%Y-%m-%d_%H%M"), bezpieczna))
    f.save(sciezka)

    ok, brak, _znalezione = plik_mod.sprawdz_naglowki(sciezka)
    if not ok:
        flash("To nie wygląda na eksport z rspo.gov.pl — brakuje kolumn: %s"
              % ", ".join(brak), "err")
        return None

    woj = None if request.form.get("zakres") == "polska" else db.WOJEWODZTWO_DOMYSLNE
    raport = magazyn.wgraj(sciezka, bezpieczna, wojewodztwo=woj,
                           wykryj_znikniete=request.form.get("znikniete") == "1",
                           conn=conn)
    flash("Wgrano %s: nowych %d, zmienionych %d, bez zmian %d."
          % (bezpieczna, raport["nowych"], raport["zmienionych"], raport["bez_zmian"]),
          "ok")
    return raport


@app.get("/import/<int:import_id>")
def import_szczegoly(import_id):
    conn = _polaczenie()
    try:
        i = conn.execute("SELECT * FROM importy WHERE id=?", (import_id,)).fetchone()
        if not i:
            flash("Nie ma takiego importu.", "err")
            return redirect(url_for("import_view"))
        return render_template("import_szczegoly.html", i=dict(i),
                               zmiany=magazyn.zmiany_importu(conn, import_id),
                               nav="import")
    finally:
        conn.close()


# --------------------------------------------------------------------- eksport

@app.get("/eksport")
def eksport_view():
    conn = _polaczenie()
    try:
        f = filtry_z_zapytania()
        format_ = request.args.get("format", "wykaz")
        os.makedirs(os.path.join(db.DATA_DIR, "eksporty"), exist_ok=True)
        nazwa = eksport.nazwa_pliku(f, format_)
        sciezka = os.path.join(db.DATA_DIR, "eksporty", nazwa)
        ile = eksport.zapisz(conn, f, sciezka, format_)
        if not ile:
            flash("Filtry nie zwróciły ani jednej placówki — plik byłby pusty.", "err")
            return redirect(request.referrer or url_for("placowki"))
        return send_file(sciezka, as_attachment=True, download_name=nazwa)
    finally:
        conn.close()


# ----------------------------------------------------------------------- start

@app.errorhandler(413)
def za_duzy(_e):
    return ("Plik jest większy niż 250 MB — to na pewno nie jest eksport z RSPO "
            "(cała Polska waży ok. 42 MB).", 413)


def main():
    db.zaloz()
    conn = db.polacz()
    try:
        ile = rejony.zasiej(conn)
        if ile:
            print("Założono %d rejonów startowych (lista Kasi z 08.08.2026)." % ile)
        w_bazie = conn.execute("SELECT COUNT(*) FROM placowki").fetchone()[0]
    finally:
        conn.close()

    port = int(os.environ.get("PORT", PORT_DOMYSLNY))
    print("\n  RSPO — narzędzie do zarządzania bazą placówek")
    print("  baza:      %s  (%d placówek)" % (db.DB_PATH, w_bazie))
    print("  adres:     http://127.0.0.1:%d" % port)
    if not w_bazie:
        print("  ZACZNIJ OD: http://127.0.0.1:%d/import — wgraj plik z rspo.gov.pl" % port)
    print()
    app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    main()
