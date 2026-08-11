#!/usr/bin/env bash
#
# Wdrożenie nowej wersji na VPS: kopia + git pull + przebudowa + sprawdzenie,
# że aplikacja naprawdę wstała.
#
#     ./wdroz.sh
#
# Po co skrypt zamiast trzech poleceń z palca: bo za trzecim razem ktoś pominie
# sprawdzenie i zostawi kontener, który się nie podniósł. Tu brak odpowiedzi
# z aplikacji kończy się czerwonym komunikatem i kodem błędu.
set -euo pipefail

USLUGA=rspo
PORT=5310

cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "BŁĄD: brak pliku .env (SECRET_KEY)."
    echo "      cp .env.example .env && nano .env && chmod 600 .env"
    exit 1
fi

# Kopia PRZED aktualizacją, nie po. Jeśli nowa wersja zrobi coś złego danym,
# po jej starcie jest już za późno. Flagi „objęta działaniem”, notatki
# i poszerzone rejony nie wracają z żadnego pliku rejestru.
echo "== kopia bazy przed aktualizacją =="
docker compose exec -T "$USLUGA" python narzedzia/kopia.py zrob --trzymaj 30 \
    || echo "UWAGA: kopia się nie udała (kontener nie działa? pierwsze wdrożenie?)"

echo "== git pull =="
git pull --ff-only

echo "== przebudowa $USLUGA =="
docker compose up -d --build "$USLUGA"

echo "== czekam, aż aplikacja odpowie =="
for i in $(seq 1 20); do
    KOD=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/" || true)
    if [ "$KOD" = "200" ]; then
        echo "OK — $USLUGA odpowiada na porcie $PORT"
        # Port ma być na 127.0.0.1. Publikowany na 0.0.0.0 omija nginx, czyli
        # także HTTPS i hasło — a ufw tego nie zasłoni, bo docker pisze wprost
        # do iptables. Sprawdzamy przy każdym wdrożeniu, bo to jedna literówka
        # w compose i nic tego nie zgłosi.
        if docker compose port "$USLUGA" 5000 | grep -q '^127.0.0.1:'; then
            exit 0
        fi
        echo "UWAGA: port $PORT jest wystawiony na świat (nie 127.0.0.1) —"
        echo "       aplikacja wisi pod http://IP:$PORT z pominięciem nginx."
        exit 1
    fi
    sleep 1
done

echo "BŁĄD: $USLUGA nie odpowiada na porcie $PORT (ostatni kod: ${KOD:-brak})."
echo "      docker compose logs --tail 50 $USLUGA"
exit 1
