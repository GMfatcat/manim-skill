FROM manimcommunity/manim:v0.20.1

USER root
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY . /opt/manim-skill
RUN pip install --no-cache-dir /opt/manim-skill
USER manimuser
