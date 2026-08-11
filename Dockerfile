FROM python:3.13-slim

# RSPO_DATA, a nie DATA_DIR — tak nazywa to `db.py` i tak stoi w README.
# Baza, wgrane pliki i eksporty lądują w /data, czyli w wolumenie: przebudowa
# obrazu ma nie ruszać tego, co koordynatorka wgrała w zeszłym miesiącu.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RSPO_DATA=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 5000

# --timeout 900, a nie domyślne 30: wgranie pliku z całej Polski to 56 190
# wierszy do przeliczenia i zapisania. Przy domyślnym limicie gunicorn ubija
# własnego workera w połowie importu, a w przeglądarce wygląda to na zerwane
# połączenie — czyli na awarię serwera, a nie na za krótki timeout.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "900", "app:app"]
