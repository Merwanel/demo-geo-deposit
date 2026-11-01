#!/bin/bash
set -euo pipefail

wait_for_icat() {
  echo "Waiting for icat:5432..."
  until pg_isready -h icat -p 5432 -U irods -d ICAT >/dev/null 2>&1; do
    sleep 2
  done
  echo "icat is ready."
}

ensure_service_account() {
  if ! getent group irods >/dev/null; then
    groupadd --system irods
  fi
  if ! getent passwd irods >/dev/null; then
    useradd --system --gid irods --home-dir /var/lib/irods --shell /bin/bash irods
  fi
}

bootstrap_volumes() {
  if [[ ! -e /var/lib/irods/scripts ]]; then
    echo "Bootstrapping /var/lib/irods from image..."
    cp -a /opt/irods_var_dist/. /var/lib/irods/
  fi
  if [[ -z "$(ls -A /etc/irods 2>/dev/null || true)" ]]; then
    echo "Bootstrapping /etc/irods from image..."
    cp -a /opt/irods_etc_dist/. /etc/irods/ 2>/dev/null || mkdir -p /etc/irods
  fi
  chown -R irods:irods /var/lib/irods /etc/irods
}

start_irods() {
  echo "Starting iRODS..."
  su - irods -c "/var/lib/irods/irodsctl start"
}

keep_alive() {
  # irodsctl daemonizes; keep the container in the foreground.
  touch /var/lib/irods/log/rodsLog.docker
  chown irods:irods /var/lib/irods/log/rodsLog.docker
  exec tail -F /var/lib/irods/log/rodsLog*
}

ensure_service_account
bootstrap_volumes
wait_for_icat

if [[ ! -f /var/lib/irods/.irods/irods_environment.json ]]; then
  echo "Running iRODS setup..."
  python3 /var/lib/irods/scripts/setup_irods.py \
    --json_configuration_file /opt/setup_irods.json
  # setup_irods.py stops the server after the post-install test.
fi

start_irods
keep_alive
