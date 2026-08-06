#!/usr/bin/env bash
set -euo pipefail

output_file=""
authorization_seen=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output)
            output_file="$2"
            shift 2
            ;;
        --header)
            if [[ "$2" == "Authorization: Bearer "* ]]; then
                authorization_seen=true
            fi
            shift 2
            ;;
        --write-out | --silent | --show-error)
            if [[ "$1" == "--write-out" ]]; then
                shift 2
            else
                shift
            fi
            ;;
        *)
            shift
            ;;
    esac
done

[[ -n "$output_file" ]] || exit 90
[[ "$authorization_seen" == true ]] || exit 91
printf '%s' "${FAKE_CENTRAL_NAMESPACE_RESPONSE:-[]}" >"$output_file"
printf '%s' "${FAKE_CENTRAL_NAMESPACE_HTTP_CODE:-200}"
exit "${FAKE_CENTRAL_NAMESPACE_CURL_STATUS:-0}"
