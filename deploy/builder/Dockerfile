# Builds the Hugo site from GitHub and rebuilds it when GitHub calls the webhook.
FROM debian:trixie-slim

# Pin tool versions; bump deliberately (and test locally with the same Hugo version).
ARG HUGO_VERSION=0.167.0
ARG WEBHOOK_VERSION=2.8.3
ARG TARGETARCH

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-${TARGETARCH}.tar.gz" \
    | tar -xz -C /usr/local/bin hugo \
 && curl -fsSL "https://github.com/adnanh/webhook/releases/download/${WEBHOOK_VERSION}/webhook-linux-${TARGETARCH}.tar.gz" \
    | tar -xz --strip-components=1 -C /usr/local/bin "webhook-linux-${TARGETARCH}/webhook" \
 && useradd --uid 1000 --create-home builder \
 && mkdir -p /srv/repo /srv/site \
 && chown builder:builder /srv/repo /srv/site

COPY --chmod=755 build.sh entrypoint.sh /app/
COPY hooks.json /app/

USER builder
EXPOSE 9000
ENTRYPOINT ["/app/entrypoint.sh"]
