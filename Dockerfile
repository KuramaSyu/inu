FROM ubuntu:latest
FROM python:3.10.4
# install rustc for lavasnek_rs and firefox-esr for selenium
USER root
RUN apt update;apt-get install -y rustc sudo firefox-esr
# manually install qalc since it is used by inu
RUN wget https://github.com/Qalculate/qalculate-gtk/releases/download/v4.5.1/qalculate-4.5.1-x86_64.tar.xz
RUN tar -xf qalculate-4.5.1-x86_64.tar.xz
RUN cp qalculate-4.5.1/qalc /usr/bin/qalc

RUN useradd -ms /bin/bash inu
RUN usermod -aG sudo inu
WORKDIR /root
#USER inu
ADD requirements.txt requirements.txt
RUN pip install asyncpg matplotlib
RUN pip install -r requirements.txt
COPY . .
RUN mkdir .config
RUN mkdir .config/qalculate
RUN cp -r dependencies/conf/qalc.cfg /root/.config/qalculate/qalc.cfg

# RUN chown -R inu: /home/inu/.config
# RUN chown -R inu: /home/inu/inu
#RUN chmod -R 777 /home/inu/
#WORKDIR /home/inu
CMD ["python3", "-O", "inu/main.py"]