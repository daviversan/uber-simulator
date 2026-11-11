FROM python:3.11-slim

# Mesmo tratamento de certificados de proxy corporativo do backend/Dockerfile.
COPY certs/ /usr/local/share/ca-certificates/
RUN update-ca-certificates
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY simulator.py driver.py telemetry.py cities.py .

RUN adduser --disabled-password appuser
USER appuser

CMD ["python", "simulator.py"]
