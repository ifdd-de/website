#!/usr/bin/env bash
# Smoke test of a running ifdd.de container (or any server with
# nginx/default.conf). Sends the Host headers the TLS endpoint would send.
#
# Usage: tests/smoke.sh [BASE_URL]   (default http://127.0.0.1:8080)
set -euo pipefail

base=${1:-http://127.0.0.1:8080}
fail=0

# check HOST PATH STATUS [LOCATION] [BODY_SUBSTRING]
check() {
    local host=$1 path=$2 status=$3 location=${4:-} body=${5:-}
    local out headers got loc
    out=$(mktemp)
    headers=$(curl -sS -o "$out" -D - -H "Host: $host" "$base$path")
    got=$(printf '%s' "$headers" | head -n1 | awk '{print $2}')
    loc=$(printf '%s' "$headers" | tr -d '\r' | awk 'tolower($1)=="location:" {print $2}')
    if [ "$got" != "$status" ]; then
        echo "FAIL $host$path: status $got, expected $status"
        fail=1
    elif [ -n "$location" ] && [ "$loc" != "$location" ]; then
        echo "FAIL $host$path: Location '$loc', expected '$location'"
        fail=1
    elif [ -n "$body" ] && ! grep -qF -- "$body" "$out"; then
        echo "FAIL $host$path: body lacks '$body'"
        fail=1
    elif printf '%s' "$headers" | grep -qiE '^server: nginx/[0-9]'; then
        echo "FAIL $host$path: Server header shows the nginx version"
        fail=1
    else
        echo "ok   $host$path -> $got${loc:+ $loc}"
    fi
    rm -f "$out"
}

check ifdd.de /                 200 "" '<html lang="en">'
check ifdd.de /de/              200 "" '<html lang="de">'
check ifdd.de /example/         200 "" 'example namespace'
check ifdd.de /de/example/      200 "" 'Beispiel-Namensraum'
check ifdd.de /packages/        200 "" 'ifdd-be-core'
check ifdd.de /repositories/    200 "" 'tools-pentest'
check ifdd.de /example          301 /example/
check ifdd.de /assets/style.css 200 "" ':root'
check ifdd.de /impressum/       200 "" '<html lang="de">'
check ifdd.de /datenschutz/     200 "" '<html lang="de">'
check ifdd.de /impressum        301 /impressum/
check ifdd.de /no-such-page     404 "" 'Page not found'
check ifdd.de /healthz          200 "" ok
check www.ifdd.de /packages/?x=1 301 'https://ifdd.de/packages/?x=1'
check example.ifdd.de /         302 https://ifdd.de/example/
check example.ifdd.de /anything 302 https://ifdd.de/example/

if [ "$fail" -ne 0 ]; then
    echo "smoke test FAILED"
    exit 1
fi
echo "smoke test passed"
