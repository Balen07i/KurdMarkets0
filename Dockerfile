FROM python:3.12-slim

WORKDIR /app

COPY requirements-2.txt .

RUN pip install --no-cache-dir -r requirements-2.txt

COPY . .

CMD ["python", "bot.py"]
