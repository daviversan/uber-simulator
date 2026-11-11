FROM python:3.11-slim

# Proxy corporativo com inspeção de TLS (ex.: Zscaler): os .crt colocados em
# certs/ passam a ser confiáveis no container. Sem proxy, a pasta fica vazia e
# este passo não faz nada. PIP_CERT faz o pip usar esses certificados também
# (por padrão ele usa uma lista própria e ignora a do sistema).
COPY certs/ /usr/local/share/ca-certificates/
RUN update-ca-certificates
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN adduser --disabled-password appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
