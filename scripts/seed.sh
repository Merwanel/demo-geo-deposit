#!/bin/sh
# Deposit the sample GeoJSON once the API is up.
set -eu

API_BASE_URL="${API_BASE_URL:-http://api}"
SAMPLE_FILE="${SAMPLE_FILE:-/samples/two-cities.geojson}"

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

echo "Seeding catalog with ${SAMPLE_FILE}..."
code="$(
  curl -sS -o /tmp/seed-response.json -w "%{http_code}" \
    -F "file=@${SAMPLE_FILE}" \
    -F "title=Paris and Lyon" \
    -F "author=Demo author" \
    -F "license=CC BY 4.0" \
    -F "abstract=A point in Paris and a point in Lyon." \
    "${API_BASE_URL}/deposits"
)"

cat /tmp/seed-response.json
echo
echo "HTTP ${code}"


# HTTP 201 (created) and 409 (already seeded) both count as success.
case "${code}" in
  201 | 409) exit 0 ;;
  *) exit 1 ;;
esac
