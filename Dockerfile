FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Criar diretório para os dados
RUN mkdir -p /app/data

EXPOSE 5003

CMD ["gunicorn", "--bind", "0.0.0.0:5003", "app:app"]