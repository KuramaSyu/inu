FROM fredboat/lavalink:dev
COPY application.yml /opt/Lavalink/application.yml
EXPOSE 2333:2333
RUN sudo apt install -y net-tools
RUN netstat -nr | grep '^0\.0\.0\.0' | awk '{print $2" dockerhost"}' >> /etc/hosts