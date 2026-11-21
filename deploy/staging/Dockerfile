# Small derived release: no package installation, dependency updates or web rebuild.
FROM ghcr.io/learnhouse/app@sha256:0aca30cd7b772bebfb75c8e4e54613ab4391adb2d4e05403992867388169514f
ARG SOURCE_REVISION
LABEL org.opencontainers.image.source="https://github.com/jakkzz/coursemax-learnhouse" \
      org.opencontainers.image.revision="${SOURCE_REVISION}"
COPY apps/api/src/services/auth/provider_proof.py \
     apps/api/src/services/auth/oauth_transactions.py \
     apps/api/src/services/auth/provider_identities.py \
     apps/api/src/services/auth/google_handoff.py /app/api/src/services/auth/
COPY apps/api/src/db/provider_identity.py /app/api/src/db/provider_identity.py
COPY apps/api/migrations/versions/c71a02d9ef40_provider_identity_ownership.py /app/api/migrations/versions/
COPY apps/web/server-wrapper.js /app/web/server-wrapper.js
COPY docker/nginx.conf /etc/nginx/http.d/default.conf
