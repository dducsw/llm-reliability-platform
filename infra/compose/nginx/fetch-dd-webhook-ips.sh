#!/usr/bin/env sh
# Sinh allowlist nginx cho dải IP webhook của Datadog: allow ...; deny all;
# Dùng: DD_SITE=datadoghq.com ./fetch-dd-webhook-ips.sh  (rồi restart nginx)
set -eu
site="${DD_SITE:-datadoghq.com}"
out="$(dirname "$0")/allow/datadog-webhooks.conf"
mkdir -p "$(dirname "$out")"
tmp="$(mktemp)"
curl -fsS "https://ip-ranges.${site}" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin)["webhooks"]; [print(f"allow {p};") for k in ("prefixes_ipv4","prefixes_ipv6") for p in d.get(k,[])]' \
  > "$tmp"
[ -s "$tmp" ] || { echo "no webhook prefixes for ${site}" >&2; rm -f "$tmp"; exit 1; }
echo "deny all;" >> "$tmp"
mv "$tmp" "$out"
echo "wrote $(grep -c '^allow' "$out") prefixes to $out"
