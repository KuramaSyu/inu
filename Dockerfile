FROM ubuntu:20.04
FROM python:3.9
ADD requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY . .
CMD [ "sh", "entry.sh" ]