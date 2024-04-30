# FROM fredboat/lavalink:dev
# COPY application.yml /opt/Lavalink/application.yml
# EXPOSE 2333:2333
FROM ubuntu:22.04
RUN apt-get update -y && apt-get upgrade -y && apt-get dist-upgrade
RUN apt install openjdk-17-jre-headless/jammy-updates -y
COPY application.yml application.yml
COPY Lavalink.jar Lavalink.jar
#CMD ["apt", "search", "openjdk-17"]
CMD [ "java", "-jar", "Lavalink.jar" ]
