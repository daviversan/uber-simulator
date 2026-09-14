FROM python:3.11-slim

# Confia em certificado(s) extra(s) de proxy corporativo com inspeção de TLS
# (ex.: Zscaler). backend/certs/ é versionado (mantém .gitkeep), mas os .crt
# dentro dela ficam fora do git — cada dev usa o seu quando precisar. Em máquinas
# sem proxy corporativo a pasta fica vazia e este passo não tem efeito nenhum.
COPY certs/ /usr/local/share/ca-certificates/
RUN update-ca-certificates

# O pip vem com sua própria lista de certificados embutida (pacote certifi) e
# ignora o repositório do sistema por padrão — então o update-ca-certificates
# acima, sozinho, não é suficiente. Esta variável manda o pip usar o bundle do
# sistema (que agora inclui o certificado extra, se houver).
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
