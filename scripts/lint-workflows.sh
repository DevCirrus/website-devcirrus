#!/usr/bin/env bash
set -euo pipefail
lint_tmp=$(mktemp -d)
trap 'rm -rf "$lint_tmp"' EXIT
curl --fail --silent --show-error --location \
  https://github.com/rhysd/actionlint/releases/download/v1.7.7/actionlint_1.7.7_linux_amd64.tar.gz \
  -o "$lint_tmp/actionlint.tar.gz"
printf '%s  %s\n' 023070a287cd8cccd71515fedc843f1985bf96c436b7effaecce67290e7e0757 "$lint_tmp/actionlint.tar.gz" | sha256sum --check --status
tar -xzf "$lint_tmp/actionlint.tar.gz" -C "$lint_tmp" actionlint
"$lint_tmp/actionlint" -shellcheck=''
