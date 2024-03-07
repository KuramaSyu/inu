FROM ubuntu:noble

FROM python:3.10.4

# Install pip
RUN python -m ensurepip

# Upgrade pip to the latest version
RUN python -m pip install --upgrade pip

# Get Rust
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y

ENV PATH="/root/.cargo/bin:${PATH}"

# install firefox-esr for selenium
RUN apt update && apt-get install -y wget firefox-esr xz-utils

# manually install qalc since it is used by inu
RUN wget -O qalculate.tar.xz https://github.com/Qalculate/qalculate-gtk/releases/download/v4.5.1/qalculate-4.5.1-x86_64.tar.xz \
    && tar -xf qalculate.tar.xz \
    && rm qalculate.tar.xz \
    && mv qalculate-* qalculate \
    && cp qalculate/qalc /usr/bin/qalc

RUN useradd -ms /bin/bash inu

# Create and set permissions for /app directory
RUN mkdir /app \
    && chown -R inu:inu /app

WORKDIR /app

# Switch to inu user
# USER inu

# Copy requirements and install dependencies
ADD requirements.txt requirements.txt
RUN pip install asyncpg matplotlib
RUN pip install -r requirements.txt

# Copy application files
COPY . .

# Create qalculate config directory and copy config file
RUN mkdir -p .config/qalculate \
    && cp -r dependencies/conf/qalc.cfg .config/qalculate/qalc.cfg

CMD ["python3", "-O", "inu/main.py"]
