#!/bin/sh
# Deposit the seeding GeoJSON samples once the API is up.
set -eu

API_BASE_URL="${API_BASE_URL:-http://api}"

echo "Waiting for API at ${API_BASE_URL}..."
i=0
until curl -sf "${API_BASE_URL}/docs" >/dev/null; do
  i=$((i + 1))
  if [ "$i" -gt 60 ]; then
    echo "API did not become ready in time." >&2
    exit 1
  fi
  sleep 2
done

deposit() {
  sample_file="$1"
  title="$2"
  abstract="$3"

  echo "Seeding catalog with ${sample_file}..."
  code="$(
    curl -sS -o /tmp/seed-response.json -w "%{http_code}" \
      -F "file=@${sample_file}" \
      -F "title=${title}" \
      -F "author=Demo author" \
      -F "license=CC BY 4.0" \
      -F "abstract=${abstract}" \
      "${API_BASE_URL}/deposits"
  )"

  cat /tmp/seed-response.json
  echo
  echo "HTTP ${code}"

  # HTTP 201 (created) and 409 (already seeded) both count as success.
  case "${code}" in
    201 | 409) ;;
    *) return 1 ;;
  esac
}

deposit /samples/marseille-nice.geojson \
  "Marseille and Nice" \
  "A point in Marseille and a point in Nice."

deposit /samples/bordeaux-toulouse.geojson \
  "Bordeaux and Toulouse" \
  "A point in Bordeaux and a point in Toulouse."
