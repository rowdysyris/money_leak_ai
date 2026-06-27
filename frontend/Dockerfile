FROM node:20-bookworm-slim AS builder

WORKDIR /app

ENV CI=true
ENV npm_config_audit=false
ENV npm_config_fund=false

RUN npm install -g npm@10.9.2

COPY package.json package-lock.json ./

RUN npm ci --include=dev --no-audit --no-fund --legacy-peer-deps

COPY . .

RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
