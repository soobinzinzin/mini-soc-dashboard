FROM kalilinux/kali-rolling
RUN apt-get update && apt-get install -y nmap hydra hping3 iputils-ping wordlists && \
    gunzip -k /usr/share/wordlists/rockyou.txt.gz && \
    rm -rf /var/lib/apt/lists/*
COPY demo_traffic.sh /root/
RUN chmod +x /root/demo_traffic.sh

CMD ["sleep", "infinity"]
