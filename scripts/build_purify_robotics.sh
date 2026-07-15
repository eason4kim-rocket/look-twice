#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="${1:-${repo_root}/purify_robotics/bin}"
mkdir -p "${output_dir}"

pushd "${repo_root}/purify_robotics" >/dev/null
go test ./...
CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" \
  -o "${output_dir}/purify-robotics-core" ./cmd/purify-robotics-core
popd >/dev/null

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "${output_dir}/purify-robotics-core" > "${output_dir}/purify-robotics-core.sha256"
else
  shasum -a 256 "${output_dir}/purify-robotics-core" > "${output_dir}/purify-robotics-core.sha256"
fi

printf 'built %s\n' "${output_dir}/purify-robotics-core"
