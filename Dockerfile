# Imagem base com Python slim
FROM python:3.11-slim

# Instalar dependências de sistema para OpenCV e MediaPipe
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgl1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Diretório de trabalho
WORKDIR /app

# Copiar e instalar dependências Python primeiro (aproveita cache do Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o restante do projeto
COPY . .

# Criar diretórios necessários em runtime
RUN mkdir -p uploads public/annotated models

# Expor porta (Railway injeta a variável PORT)
EXPOSE 8000

# Comando de inicialização
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
