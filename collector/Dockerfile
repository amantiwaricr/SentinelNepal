# Lab collector image (TShark + sentinel_ml + sentinel_collector). Also runs the separate
# "capture" service, which only uses dumpcap. Build context is the repository root.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# tshark brings dumpcap. Instead of the setuid helper, dumpcap gets only CAP_NET_RAW as a
# file capability; it takes effect only where the container grants NET_RAW (the "capture"
# service). The collector service grants nothing, so there it cannot capture at all.
RUN echo "wireshark-common wireshark-common/install-setuid boolean false" | debconf-set-selections \
 && apt-get update \
 && apt-get install -y --no-install-recommends tshark libcap2-bin \
 && setcap cap_net_raw=eip /usr/bin/dumpcap \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY ml/requirements.txt ml/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --retries 10 --timeout 60 -r ml/requirements.txt

COPY ml/pyproject.toml ml/pyproject.toml
COPY ml/sentinel_ml ml/sentinel_ml
COPY collector/pyproject.toml collector/pyproject.toml
COPY collector/sentinel_collector collector/sentinel_collector
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --retries 10 --timeout 60 --no-deps ./ml ./collector

# Capture and collector both run as this unprivileged user, so the collector can read the
# capture files dumpcap writes (mode 0600). The collector has no access to the lab network.
RUN useradd --create-home --uid 10002 --shell /usr/sbin/nologin collector \
 && mkdir /captures && chown collector:collector /captures
USER collector
CMD ["sentinel-collector", "run"]
