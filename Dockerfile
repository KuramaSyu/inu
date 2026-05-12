FROM python:3.13-bookworm

# install firefox-esr for selenium
# install texlive for matplotlib
# install qalculate for qalc
RUN apt-get update && apt-get install -y --no-install-recommends \
    firefox-esr \
    qalculate-gtk \
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-latex-extra \
    pipx \
    dvipng \
    cm-super && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Add user inu - this is needed, since qalc config 
# needs to be in a home directory, not root
RUN useradd -ms /bin/bash inu

# Create and set permissions for /home/inu/app directory
USER inu
WORKDIR /home/inu
ENV PIPX_HOME="/home/inu/.local/pipx"
ENV PIPX_BIN_DIR="/home/inu/.local/bin"
ENV PATH="/home/inu/.local/bin:${PATH}"
RUN pipx install uv

# Copy project metadata and install dependencies with uv
COPY --chown=inu:inu pyproject.toml pyproject.toml

# install dependencies with uv
RUN uv sync

# Copy application files
COPY --chown=inu:inu dependencies dependencies
COPY --chown=inu:inu inu inu
COPY --chown=inu:inu config.yaml config.yaml

# Create qalculate config directory and copy config file
RUN mkdir -p .config/qalculate \
    && cp -r dependencies/conf/qalc.cfg .config/qalculate/qalc.cfg

USER root
# Create log directory and set permissions
RUN mkdir -p inu \
    && chown -R inu:inu inu
USER inu

#CMD ["python3", "-O", "inu/main.py"]
CMD ["uv",  "run", "--", "python", "-O", "-m", "inu.main"]
