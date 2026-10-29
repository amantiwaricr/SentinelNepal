# Lab "server": a small web server and an SSH server for the client to talk to.
# Isolated lab only: it sits on an internal Docker network with no internet access.
# nginx listens on IPv4 only, because some Docker setups give containers no IPv6.
FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx openssh-server \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /run/sshd \
 && ssh-keygen -A \
 && printf 'SentinelNepal lab web server\n' > /var/www/html/index.html \
 && printf 'about page\n' > /var/www/html/about.html \
 && sed -i '/listen \[::\]:80/d' /etc/nginx/sites-available/default
# No account has a usable password: SSH login attempts in the lab always fail, which is all
# the brute-force exercise needs.
RUN useradd --create-home --shell /bin/bash labuser && passwd -l labuser
EXPOSE 22 80
CMD ["sh", "-c", "/usr/sbin/sshd && exec nginx -g 'daemon off;'"]
