# syntax=docker/dockerfile:1.7
# Build Node, puis fichiers statiques servis par nginx (Alpine) sans privilèges root.

# ------------------------------------------------------------------ build
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# ---------------------------------------------------------------- runtime
# nginx d'Alpine plutôt que l'image nginx officielle : Alpine publie ses correctifs
# de sécurité (paquets -rN) plus vite que l'étiquette 1.28 de l'image officielle,
# restée sur une version vulnérable.
FROM alpine:3.23 AS runtime

RUN apk upgrade --no-cache \
 && apk add --no-cache nginx \
 && mkdir -p /etc/nginx/conf.d /etc/nginx/snippets

COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html

# Utilisateur non privilégié créé par le paquet nginx ; le port 8080 ne demande pas root.
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1

# -e stderr : nginx n'essaie pas d'ouvrir son journal par défaut avant de lire la config.
CMD ["nginx", "-e", "stderr", "-g", "daemon off;"]
