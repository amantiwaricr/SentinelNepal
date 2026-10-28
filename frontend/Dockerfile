# Development image for the frontend: runs the Vite dev server with the /api proxy.
# A production build (static files behind a web server) is part of Phase 8.
FROM node:22-alpine

WORKDIR /app
RUN chown node:node /app
USER node

COPY --chown=node:node frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY --chown=node:node frontend/ ./

EXPOSE 5173
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
  CMD ["wget", "-q", "--spider", "http://127.0.0.1:5173/"]

CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "5173"]
