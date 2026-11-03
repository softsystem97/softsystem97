#!/usr/bin/env bash
# Disposable GitHub Actions database: TLS is required and its CA is pinned.
set -euo pipefail
if [[ "${GITHUB_ACTIONS:-}" != "true" ]]; then
  echo "This script only provisions the disposable GitHub Actions database."
  exit 1
fi
: "${SS97_CI_DB_PASSWORD:?CI database password required}"
ss97_tls_dir="${RUNNER_TEMP:?}/ss97-db-tls"
umask 077
mkdir -p "$ss97_tls_dir"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj '/CN=SS97 disposable CI CA' \
  -keyout "$ss97_tls_dir/ca-key.pem" -out "$ss97_tls_dir/ca.pem" 2>/dev/null
openssl req -newkey rsa:2048 -nodes -subj '/CN=localhost' \
  -keyout "$ss97_tls_dir/server-key.pem" -out "$ss97_tls_dir/server.csr" 2>/dev/null
printf 'subjectAltName=IP:127.0.0.1,DNS:localhost\nextendedKeyUsage=serverAuth\n' > "$ss97_tls_dir/server.ext"
openssl x509 -req -days 1 -in "$ss97_tls_dir/server.csr" \
  -CA "$ss97_tls_dir/ca.pem" -CAkey "$ss97_tls_dir/ca-key.pem" -CAcreateserial \
  -extfile "$ss97_tls_dir/server.ext" -out "$ss97_tls_dir/server-cert.pem" 2>/dev/null
chmod 644 "$ss97_tls_dir/ca.pem" "$ss97_tls_dir/server-cert.pem"
ss97_mysql_uid=$(docker run --rm --entrypoint id mariadb:11.4 -u mysql)
ss97_mysql_gid=$(docker run --rm --entrypoint id mariadb:11.4 -g mysql)
sudo chown "$ss97_mysql_uid:$ss97_mysql_gid" "$ss97_tls_dir/server-key.pem"
# The service user can traverse the mount but only it can read the server key.
chmod 755 "$ss97_tls_dir"
docker run --detach --name ss97-db --publish 127.0.0.1:3306:3306 \
  --env "MARIADB_ROOT_PASSWORD=$SS97_CI_DB_PASSWORD" \
  --volume "$ss97_tls_dir:/etc/mysql/ss97-tls:ro" mariadb:11.4 \
  --ssl-ca=/etc/mysql/ss97-tls/ca.pem --ssl-cert=/etc/mysql/ss97-tls/server-cert.pem \
  --ssl-key=/etc/mysql/ss97-tls/server-key.pem --require-secure-transport=ON \
  --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
for ss97_attempt in {1..45}; do
  if docker exec ss97-db healthcheck.sh --connect --innodb_initialized; then
    break
  fi
  if [[ "$ss97_attempt" == 45 ]]; then docker logs ss97-db; exit 1; fi
  sleep 2
done
# Frappe's SQL bootstrap invokes the native client; keep its verification enabled.
printf '[client]\nssl-ca=%s\nssl-verify-server-cert\n' "$ss97_tls_dir/ca.pem" \
  | sudo tee /etc/mysql/conf.d/ss97-ci-tls.cnf >/dev/null
