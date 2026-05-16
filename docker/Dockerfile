FROM manimcommunity/manim:v0.20.1

# Universal image: the render container the worker spawns per beat AND
# the api / worker / ui compose services all run from this one image.
# ffmpeg = gif conversion + stitch; docker.io = the worker's CLI for
# spawning sibling render containers via the mounted host socket.
# docker-cli is explicitly installed because docker.io only installs the
# daemon (dockerd); the CLI binary ships in the separate docker-cli package.
USER root
# fonts-noto-cjk gives manim's Pango text path a font with CJK glyphs so
# Text("中文") renders properly (without it, every CJK codepoint comes
# out as a tofu box). The Noto CJK package covers Trad/Simp Chinese,
# Japanese, and Korean in a single fallback font family.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg docker.io docker-cli fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f
COPY . /opt/manim-skill
RUN pip install --no-cache-dir /opt/manim-skill
USER manimuser
