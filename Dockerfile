FROM ubuntu:20.04
FROM python:3.10.4
RUN apt update
RUN apt upgrade -y
RUN apt-get install -y rustc sudo
RUN apt-get install -y qalc
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