FROM node:20-alpine AS build

WORKDIR /app

# 默认留空 = 同源：生产镜像通过 nginx 反向代理 /api/* 到后端容器，
# 本机和远程服务器都能直接用。仅当前后端分域名且不经过统一反代时才需 --build-arg 显式指定。
ARG NUXT_PUBLIC_API_BASE=
ENV NUXT_PUBLIC_API_BASE=$NUXT_PUBLIC_API_BASE

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/.output/public /usr/share/nginx/html

EXPOSE 80
