FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose standard web port
EXPOSE 8000

# Run the commerce wrapper, which imports the existing JakeAI app and replaces
# the legacy checkout route with tracked free claims and verified paid delivery.
CMD ["sh", "-c", "uvicorn commerce_app:app --host 0.0.0.0 --port ${PORT:-8000}"]
