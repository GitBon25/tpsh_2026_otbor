FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot
COPY scripts ./scripts
COPY db ./db
COPY data ./data

CMD ["python", "-m", "bot.main"]