# Usar una imagen oficial de Python ligera
FROM python:3.10-slim

# Instalar dependencias del sistema necesarias para Chrome y el WebDriver
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    libnss3 \
    libxss1 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Instalar Google Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Configurar el directorio de trabajo
WORKDIR /app

# Copiar dependencias primero (para aprovechar caché de Docker)
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install uvicorn

# Copiar todo el código de la aplicación
COPY . .

# Exponer el puerto de FastAPI
EXPOSE 8000

# Comando para ejecutar la aplicación (Render inyectará la variable PORT automáticamente)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
