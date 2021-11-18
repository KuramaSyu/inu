#!/bin/bash
FROM ubuntu:20.04
RUN apt update
EXPOSE 2333:2333
COPY Lavalink.jar Lavalink.jar
COPY application.yml application.yml
COPY main.sh main.sh
RUN apt install -y net-tools
RUN apt install -y openjdk-11-jdk
# RUN apt-get update && apt-get install -y iputils-ping 
# RUN ping -c 4 www.google.de
# CMD ["sh", "main.sh"]
CMD ["java", "-jar", "Lavalink.jar"]