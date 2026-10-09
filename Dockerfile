FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/symptosense/app

# pg_dump / pg_restore are required by SymptoSense encrypted backup/restore.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .

# Rebuild browser asset folders from the flat release layout.
# This keeps /static/... and /icons/... reliable on fresh Railway images.
RUN set -eu; \
    mkdir -p static/js static/css static/images icons; \
    cp -f interaction-bridge.js manage-profile.js mini-charts.js offline.js static/js/; \
    cp -f design-system.css offline.css v83_user_tools.css app-shell-v111.css static/css/; \
    cp -f symptosense-social-preview.png safeid-add-to-phone-guide.png about-hero.webp about-home-preview.webp about-story.webp about-us-concept-v3.webp ss-hero-body-v132.webp body-map-front-v241.png body-front-v245.webp body-back-v245.webp static/images/; \
    cp -f icon-192.png icon-512.png apple-touch-icon.png icon.svg about-us-phone.webp icons/

ARG ALLOW_UNSIGNED_CLINICAL=0

# Build only fails for files that are truly required to start the web service.
# Competition/QA metadata is useful but optional; a partial GitHub web upload
# must not take the whole production service offline because one optional JSON
# fixture was omitted.
RUN set -eu; \
    echo "SymptoSense Railway build profile: V272"; \
    python -m pip check; \
    python -m py_compile railway_entrypoint.py railway_runtime.py webapp.py lab_intake.py blood_test.py; \
    for f in railway.json requirements.txt railway_entrypoint.py railway_runtime.py webapp.py lab_intake.py blood_test.py chat_view.py site_info_view.py service-worker.js manifest.webmanifest; do \
      if [ ! -s "$f" ]; then echo "ERROR: required runtime file missing or empty: $f" >&2; exit 1; fi; \
    done; \
    if [ ! -s release_metrics.json ]; then echo "WARNING: release_metrics.json missing; competition metrics will fall back safely"; fi; \
    if [ ! -s safety_cases.json ] && [ ! -s runtime_data/safety_cases.json ]; then echo "WARNING: safety case fixture missing; Safety Twin will show no synthetic cases until restored"; fi; \
    if grep -Eq '^[[:space:]]*(from|import)[[:space:]]+views([.]|[[:space:]])' webapp.py chat_view.py site_info_view.py; then \
      echo "ERROR: production runtime still depends on the optional views/ package" >&2; exit 1; \
    fi; \
    if [ "${ALLOW_UNSIGNED_CLINICAL:-0}" = "1" ]; then \
      echo "WARNING: clinical sign-off gate OVERRIDDEN by ALLOW_UNSIGNED_CLINICAL=1"; \
      date -u +%Y-%m-%dT%H:%M:%SZ > .clinical_bypass; \
    else \
      python tools/signoff.py check --strict || { echo "ERROR: clinical sign-off pending; see clinical_signoff.json (override only deliberately: --build-arg ALLOW_UNSIGNED_CLINICAL=1)" >&2; exit 1; }; \
    fi; \
    echo "SymptoSense V272 production build validation passed"

EXPOSE 5000

CMD ["python", "railway_entrypoint.py"]
