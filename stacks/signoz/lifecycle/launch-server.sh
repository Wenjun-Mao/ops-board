#!/bin/sh
set -eu

if [ "$#" -lt 2 ]; then
  printf 'Expected JWT secret file and server command\n' >&2
  exit 64
fi
secret_file=$1
shift
if [ ! -r "$secret_file" ] || ! secret=$(cat "$secret_file" 2>/dev/null) || [ -z "$secret" ]; then
  printf 'SigNoz JWT secret must be readable and nonempty; server not started\n' >&2
  exit 78
fi
export SIGNOZ_TOKENIZER_JWT_SECRET="$secret"
unset secret
exec "$@"
