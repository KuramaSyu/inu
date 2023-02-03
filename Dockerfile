

FROM archlinux:latest
FROM python:3.10.4
RUN pacman -Syu
RUN pacman -S qalc rustc
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