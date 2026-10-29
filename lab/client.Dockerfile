# Lab "client": generates traffic towards lab-server only (see scripts/).
FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl nmap openssh-client sshpass \
 && rm -rf /var/lib/apt/lists/*
COPY lab/scripts/ /lab/
RUN chmod 0755 /lab/*.sh
# By default: light, ordinary web browsing so there is always some normal traffic.
CMD ["/lab/normal.sh"]
