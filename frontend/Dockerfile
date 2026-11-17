# Pinned by digest: reproducible, and no registry lookup once cached. Bump tag and digest together.
FROM node:24-alpine@sha256:116b800c3754b440ee0aa3ed2f20f5bf3d99a554bfd9adeea09ea8017f6e85f5 AS build
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH
RUN npm install --global pnpm@12.11.2
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,target=/pnpm/store pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginxinc/nginx-unprivileged:1.29-alpine@sha256:0c79d56aee561a1d81c63f00eee5fb5fe29279560cdc55e91425133104c7fbe6 AS runtime
LABEL org.opencontainers.image.title="iphi-frontend" \
      org.opencontainers.image.description="IPHI dashboard behind Nginx, proxying the API" \
      org.opencontainers.image.source="https://github.com/bachiryaye/iphi"
# Rendered into /tmp: the root filesystem can stay read-only.
ENV IPHI_API_UPSTREAM=http://api:8000 \
    NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1 \
    NGINX_ENVSUBST_OUTPUT_DIR=/tmp \
    NGINX_ENVSUBST_FILTER="^(IPHI_|NGINX_LOCAL_RESOLVERS$)"
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/iphi.conf.template /etc/nginx/templates/iphi.conf.template
COPY nginx/security-headers.conf /etc/nginx/iphi/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["wget", "-q", "--spider", "http://127.0.0.1:8080/"]
