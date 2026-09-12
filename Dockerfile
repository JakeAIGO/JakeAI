FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# crypto_commerce_app imports the existing verified card commerce wrapper, then
# registers Base/native-USDC routes behind independent payment + legal gates.
# Both crypto activation flags remain OFF in production until explicitly approved.
CMD ["sh", "-c", "uvicorn crypto_commerce_app:app --host 0.0.0.0 --port ${PORT:-8000}"]
