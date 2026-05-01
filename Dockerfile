FROM python:3.9-slim-bullseye

# Dependências de sistema + Chrome em um único bloco para reduzir camadas e
# garantir que tudo é resolvido com um único `apt-get update`.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        wget \
        gnupg \
        curl \
        unzip \
        tini \
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
        xdg-utils && \
    install -d -m 0755 /etc/apt/keyrings && \
    wget -qO - https://dl.google.com/linux/linux_signing_key.pub \
        | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
        > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends google-chrome-stable && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Pré-instala o ChromeDriver compatível com a versão do Chrome (Chrome for Testing).
# Elimina a chamada de rede do `webdriver-manager` em runtime, que era ponto de hang.
RUN set -eux; \
    CHROME_VERSION="$(google-chrome --version | awk '{print $3}')"; \
    CHROME_MAJOR="$(echo "$CHROME_VERSION" | cut -d. -f1)"; \
    DRIVER_VERSION="$(curl -fsSL "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR}")"; \
    curl -fsSL -o /tmp/chromedriver.zip \
        "https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip"; \
    unzip -j /tmp/chromedriver.zip chromedriver-linux64/chromedriver -d /usr/local/bin/; \
    chmod +x /usr/local/bin/chromedriver; \
    rm /tmp/chromedriver.zip; \
    chromedriver --version

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Usuário não-root com UID/GID estáveis para evitar problemas de permissão em volumes
RUN groupadd -r scraper -g 1000 && \
    useradd -r -u 1000 -g scraper -d /home/scraper -s /bin/bash scraper && \
    mkdir -p /home/scraper && \
    chown -R scraper:scraper /home/scraper /app

USER scraper

ENV CHROME_BIN=/usr/bin/google-chrome \
    CHROME_DRIVER_PATH=/usr/local/bin/chromedriver \
    PYTHONUNBUFFERED=1

# tini como PID 1 para reaper de processos do Chrome e propagação correta de sinais
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "selenium-scraper.py"]
