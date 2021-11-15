FROM python:3.9
COPY . .
RUN pip3 install requests beautifulsoup4
CMD [ "python3", "main.py" ]