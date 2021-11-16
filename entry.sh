#!/bin/bash
apt update
apt install net-tools
echo "started"
netstat -nr | grep '^0\.0\.0\.0' | awk '{print $2" dockerhost"}'
netstat -nr | grep '^0\.0\.0\.0' | awk '{print $2" dockerhost"}' >> /etc/hosts
ifconfig
netstat -a
# python3 prepare.py
python3 inu/main.py