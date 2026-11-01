FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gpg \
        python3 \
        python3-pyodbc \
        unixodbc \
        odbc-postgresql \
        postgresql-client \
    && curl -fsSL https://packages.irods.org/irods-signing-key.asc \
        | gpg --dearmor -o /usr/share/keyrings/irods-archive-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/irods-archive-keyring.gpg] https://packages.irods.org/apt/ noble main" \
        > /etc/apt/sources.list.d/irods.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        irods-server=4.3.5-0~noble \
        irods-database-plugin-postgres=4.3.5-0~noble \
        irods-icommands=4.3.5-0~noble \
        irods-runtime=4.3.5-0~noble \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system irods \
    && useradd --system --gid irods --home-dir /var/lib/irods --shell /bin/bash irods \
    && mkdir -p /etc/irods \
    && cp -a /var/lib/irods /opt/irods_var_dist \
    && cp -a /etc/irods /opt/irods_etc_dist \
    && chown -R irods:irods /var/lib/irods /etc/irods /opt/irods_var_dist /opt/irods_etc_dist

COPY setup_irods.json /opt/setup_irods.json
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 1247

ENTRYPOINT ["/entrypoint.sh"]
