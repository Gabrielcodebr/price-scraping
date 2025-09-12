FROM python:3.9-slim-bullseye

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    unzip \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    --no-install-recommends

# Adicionar repositório do Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Instalar Chrome estável
RUN apt-get update && apt-get install -y google-chrome-stable

# Instalar ChromeDriver compatível (usando webdriver-manager via pip)
RUN apt-get install -y curl && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Criar usuário e grupo com UID/GID específicos para evitar problemas de permissão
RUN groupadd -r scraper -g 1000 && \
    useradd -r -u 1000 -g scraper -d /home/scraper -s /bin/bash scraper && \
    mkdir -p /home/scraper && \
    chown -R scraper:scraper /home/scraper && \
    chown -R scraper:scraper /app

# Mudar para usuário não-root
USER scraper

# Definir variáveis de ambiente para Chrome
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROME_DRIVER_PATH=/usr/local/bin/chromedriver

CMD ["python", "selenium-scraper.py"]