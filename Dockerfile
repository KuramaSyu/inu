FROM ubuntu:lunar
FROM python:3.10.4
RUN apt update
RUN apt upgrade -y
RUN apt-get install -y rustc sudo

# manually install qalc since it is used by inu
RUN wget https://github.com/Qalculate/qalculate-gtk/releases/download/v4.5.1/qalculate-4.5.1-x86_64.tar.xz
RUN tar -xf qalculate-4.5.1-x86_64.tar.xz
RUN cp qalculate-4.5.1/qalc /usr/bin/qalc

RUN useradd -ms /bin/bash inu
RUN usermod -aG sudo inu
WORKDIR /home/inu
USER inu
ADD requirements.txt requirements.txt
RUN pip install asyncpg matplotlib
RUN pip install -r requirements.txt
COPY . .
RUN mkdir .config
RUN mkdir .config/qalculate
RUN cp -r dependencies/conf/qalc.cfg /home/inu/.config/qalculate/qalc.cfg
USER root
RUN chown -R inu: /home/inu/.config
RUN chown -R inu: /home/inu/inu
USER inu
WORKDIR /home/inu
CMD ["python3", "inu/main.py"]