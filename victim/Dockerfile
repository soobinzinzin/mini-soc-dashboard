FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y openssh-server python3 iputils-ping && \
    mkdir /var/run/sshd && \
    useradd -m -s /bin/bash demo && echo "demo:demo123" | chpasswd && \
    rm -rf /var/lib/apt/lists/*

EXPOSE 22 80

CMD service ssh start && python3 -m http.server 80
