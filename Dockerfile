FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ffmpeg \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Install the BgUtils PO Token provider
RUN git clone --depth 1 --branch 2.0.1 \
    https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
    /opt/bgutil-ytdlp-pot-provider

# Build the provider's Node.js generation script
WORKDIR /opt/bgutil-ytdlp-pot-provider/server
RUN npm ci --omit=dev --no-audit --no-fund \
    && npx tsc

WORKDIR /app

COPY server.py .

ENV PORT=10000
ENV TOKEN_TTL=6

EXPOSE 10000

CMD ["python3", "server.py"]
