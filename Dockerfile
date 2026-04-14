FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY analisador.py .

VOLUME ["/data"]

ENV PASTA_IMAGENS=/data \
    ARQUIVO_SAIDA=Planilha_Laudos_Final.xlsx \
    ARQUIVO_CHECKPOINT=resultados_parciais.csv \
    GEMINI_MODEL=gemini-2.5-flash \
    DELAY_SECONDS=4.0 \
    TAMANHO_LOTE=10 \
    MAX_RETRIES=5

CMD ["python", "analisador.py"]
