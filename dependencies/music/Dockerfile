FROM ubuntu:20.04
RUN apt update
EXPOSE 2333:2333
COPY Lavalink.jar Lavalink.jar
COPY application.yml application.yml
COPY main.sh main.sh
RUN apt install -y net-tools
RUN apt install -y openjdk-11-jdk
RUN ifconfig
CMD ["java", "-jar", "Lavalink.jar"]