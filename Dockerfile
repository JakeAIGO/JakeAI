FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# commerce_recovery_app wraps the existing crypto/card commerce app with a narrow
# Stripe-verified recovery path for paid orders lost when ephemeral runtime storage
# resets between Checkout creation and the buyer's success redirect.
CMD ["sh", "-c", "uvicorn commerce_recovery_app:app --host 0.0.0.0 --port ${PORT:-8000}"]
