# FROM fredboat/lavalink:dev
# COPY application.yml /opt/Lavalink/application.yml
# EXPOSE 2333:2333
FROM ubuntu:20.04
RUN apt-get update -y && apt-get upgrade -y && apt-get dist-upgrade
RUN apt-get install openjdk-11-jdk -y
COPY .application.yml .application.yml
COPY .Lavalink.jar .Lavalink.jar
CMD [ "java", "-jar Lavalink.jar" ]
