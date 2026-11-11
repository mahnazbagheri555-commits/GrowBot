FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hugging Face از پورت 7860 استفاده می‌کند
EXPOSE 7860

CMD ["python", "bot.py"]
