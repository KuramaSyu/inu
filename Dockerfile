FROM ubuntu:20.04
FROM python:3.10.4
RUN apt update
RUN apt upgrade -y
RUN apt-get install -y rustc
RUN apt-get install -y qalc
ADD requirements.txt requirements.txt
RUN pip install asyncpg matplotlib
RUN pip install -r requirements.txt
COPY . .
RUN mkdir .config
RUN mkdir .config/qalculate
RUN cp -r dependencies/conf/qalc.cfg /.config/qalculate/qalc.cfg
CMD [ "sh", "entry.sh" ]