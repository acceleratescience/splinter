FROM axolotlai/axolotl-uv:main-py3.12-cu130-2.10.0

WORKDIR /app

# Install service dependencies on top of Axolotl's environment
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

COPY app/ ./app/

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${FINETUNING_PORT}"]
