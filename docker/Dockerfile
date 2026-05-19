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
        ffmpeg docker.io docker-cli fonts-noto-cjk curl \
    && rm -rf /var/lib/apt/lists/*

# IBM Plex (Latin: Sans/Serif/Mono) for the slide-deck animations in
# dlm-polish/. Without these, requests for "IBM Plex *" fall through to
# Pango's per-glyph fallback chain and Latin words pick up uneven
# kerning ("parallel" -> "para llel" gap). Not in Debian apt, so pull
# the TTFs from the IBM/plex GitHub release via jsdelivr.
ARG PLEX_VER=v6.4.0
RUN set -eux; \
    mkdir -p /usr/local/share/fonts/ibm-plex; \
    base="https://cdn.jsdelivr.net/gh/IBM/plex@${PLEX_VER}"; \
    for fam in Sans Serif Mono; do \
        for style in Regular Bold Italic BoldItalic; do \
            curl -fsSL -o "/usr/local/share/fonts/ibm-plex/IBMPlex${fam}-${style}.ttf" \
                "${base}/IBM-Plex-${fam}/fonts/complete/ttf/IBMPlex${fam}-${style}.ttf"; \
        done; \
    done; \
    fc-cache -f
COPY . /opt/manim-skill
RUN pip install --no-cache-dir /opt/manim-skill
USER manimuser
