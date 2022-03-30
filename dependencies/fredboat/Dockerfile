# FROM fredboat/lavalink:dev
# COPY application.yml /opt/Lavalink/application.yml
# EXPOSE 2333:2333
FROM ubuntu:20.04
RUN apt update
RUN apt upgrade -y
RUN apt-get isntall openjdk -y
COPY .Lavalink.jar .Lavalink.jar
COPY .application.yml .application.yml
CMD [ "java", "-jar Lavalink.jar" ]
