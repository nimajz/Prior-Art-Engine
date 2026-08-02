FROM python:3.11-slim

WORKDIR /app

# System deps needed to build a couple of wheels (sentencepiece/yake)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# CPU-only torch wheel — a fraction of the size of the default CUDA wheel,
# which matters for free-tier build time/storage limits.
RUN pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY app ./app

# Pre-download both models into the image at build time so the service
# never has to fetch them at runtime — faster, and survives free-tier
# cold starts / ephemeral filesystems cleanly.
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('BAAI/bge-small-en-v1.5'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
