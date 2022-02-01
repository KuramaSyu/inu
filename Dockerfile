FROM ubuntu:20.04
FROM python:3.8
RUN apt update
RUN apt upgrade -y
RUN apt-get install -y rustc
ADD requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY . .
CMD [ "sh", "entry.sh" ]