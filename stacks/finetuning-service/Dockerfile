FROM axolotlai/axolotl:main-py3.12-cu130-2.10.0

WORKDIR /app

# Install service dependencies on top of Axolotl's environment
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${FINETUNING_PORT}"]
