FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=run.py

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# L'application ne tourne pas en root : seul instance/ (base SQLite) lui
# est accessible en écriture
RUN useradd --create-home --uid 1000 app \
    && mkdir -p instance \
    && chown app:app instance \
    && chmod +x docker-entrypoint.sh
USER app

EXPOSE 5000

# Migrations, démo et compte du gérant (selon l'environnement), puis
# gunicorn : voir docker-entrypoint.sh
CMD ["./docker-entrypoint.sh"]
