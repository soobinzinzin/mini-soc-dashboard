FROM kalilinux/kali-rolling
RUN apt-get update && apt-get install -y nmap hydra hping3 iputils-ping wordlists && \
    gunzip -k /usr/share/wordlists/rockyou.txt.gz && \
    rm -rf /var/lib/apt/lists/*
CMD ["sleep", "infinity"]
