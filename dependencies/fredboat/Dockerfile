# FROM fredboat/lavalink:dev
# COPY application.yml /opt/Lavalink/application.yml
# EXPOSE 2333:2333
FROM ubuntu:20.04
RUN apt-get update -y && sudo apt-get upgrade -y && sudo apt-get dist-upgrade
RUN apt-get install openjdk-11-jdk -y
COPY .Lavalink.jar .Lavalink.jar
COPY .application.yml .application.yml
CMD [ "java", "-jar Lavalink.jar" ]
