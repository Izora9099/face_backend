# FACE.IT backend - same image on Linux, macOS and Windows hosts.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# dlib-bin needs the OpenBLAS/LAPACK runtime; libjpeg/zlib come with Pillow wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libopenblas0 liblapack3 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN useradd --create-home --uid 1000 app \
    && mkdir -p logs media temp backups reports \
    && chown -R app:app /app
USER app

EXPOSE 8000
ENTRYPOINT ["sh", "docker/entrypoint.sh"]
# Each worker loads the dlib models (~100 MB); scale with threads first.
CMD ["gunicorn", "face_backend.wsgi:application", "--bind", "0.0.0.0:8000", \
     "--workers", "2", "--threads", "4", "--timeout", "60", "--access-logfile", "-"]
