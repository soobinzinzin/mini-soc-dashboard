FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y snort iproute2 && \
    mkdir -p /var/log/snort && \
    rm -rf /var/lib/apt/lists/*

COPY snort.conf /etc/snort/snort.conf
COPY local.rules /etc/snort/rules/local.rules

# Snort dùng chung network namespace với container victim (xem docker-compose.yml)
CMD ["snort", "-q", "-k", "none", "-c", "/etc/snort/snort.conf", "-i", "eth0", "-A", "fast", "-l", "/var/log/snort"]
