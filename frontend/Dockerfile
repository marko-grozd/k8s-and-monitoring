# ---- Stage 1: Build ----
FROM node:20-alpine AS builder

WORKDIR /app

# Kopiramo dependency fajlove prvo (Docker cache layer optimizacija)
COPY package*.json ./
RUN npm ci --silent

# Kopiramo ostatak source-a i buildujemo
COPY . .
RUN npm run build

# ---- Stage 2: Serve ----
FROM nginx:alpine AS production

# Kopiramo nginx konfiguraciju
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

# Kopiramo build output iz prve faze
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost/nginx-health || exit 1

CMD ["nginx", "-g", "daemon off;"]
