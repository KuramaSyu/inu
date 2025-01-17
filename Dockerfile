FROM ubuntu:noble
FROM python:3.10.4
# Install pip
RUN python -m ensurepip

# Upgrade pip to the latest version
RUN python -m pip install --upgrade pip

# install firefox-esr for selenium
# install texlive for matplotlib
# install wget, ez-utils for downloading qalc
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    wget \
    firefox-esr \
    xz-utils \
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-latex-extra \
    dvipng \
    cm-super \
    zstd \
    git \
    intltool \
    autoconf \
    automake \
    libtool \
    pkg-config \
    libreadline-dev \
    libxml2-dev \
    libcurl4-openssl-dev \
    libmpfr-dev \
    libgmp-dev \
    gettext \
    ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# manually install qalc since it is used by inu
# for ARM, complie from source, since no version for download available
# for x86_64, download and extract the binary
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        wget -O qalculate.tar.xz https://github.com/Qalculate/qalculate-gtk/releases/download/v4.9.0/qalculate-4.9.0-x86_64.tar.xz; \
        tar -xf qalculate.tar.xz && \
        rm qalculate.tar.xz && \
        mv qalculate-* qalculate && \
        cp qalculate/qalc /usr/bin/qalc; \
    else \
        git clone https://github.com/Qalculate/libqalculate.git /tmp/libqalculate && \
        cd /tmp/libqalculate && \
        ./autogen.sh && \
        ./configure && \
        make && make install && \
        ldconfig && \
        rm -rf /tmp/libqalculate; \
    fi

# Add user inu - this is needed, since qalc config 
# needs to be in a home directory, not root
RUN useradd -ms /bin/bash inu

# Create and set permissions for /home/inu/app directory
USER inu
WORKDIR /home/inu
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | bash -s -- -y
ENV PATH="/home/inu/.cargo/bin:${PATH}"

# Copy requirements and install dependencies
ADD requirements.txt requirements.txt
RUN pip install asyncpg matplotlib
RUN pip install -r requirements.txt

# Copy application files
COPY dependencies dependencies
COPY inu inu
COPY config.yaml config.yaml

# Create qalculate config directory and copy config file
RUN mkdir -p .config/qalculate \
    && cp -r dependencies/conf/qalc.cfg .config/qalculate/qalc.cfg

USER root
# Create log directory and set permissions
RUN mkdir -p inu \
    && chown -R inu:inu inu
USER inu

CMD ["python3", "-O", "inu/main.py"]
