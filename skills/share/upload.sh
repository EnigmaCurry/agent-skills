#!/usr/bin/env bash
# Upload a file to S3 via rclone using the /share skill config.
# Usage: upload.sh <local-file> <remote-path>
# Example: upload.sh /tmp/claude-export.html exports/abc12345/my-conversation.html
#
# Reads config from ~/.config/claude-skills/export/config.env
# Prints the public URL on success.

set -euo pipefail

CONFIG_FILE="${HOME}/.config/claude-skills/export/config.env"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Error: config not found: $CONFIG_FILE" >&2
    echo "Run /share to set up the configuration." >&2
    exit 1
fi

source "$CONFIG_FILE"

if [[ -z "${RCLONE_REMOTE:-}" || -z "${RCLONE_BUCKET:-}" || -z "${S3_PUBLIC_URL:-}" ]]; then
    echo "Error: config incomplete. Need RCLONE_REMOTE, RCLONE_BUCKET, S3_PUBLIC_URL" >&2
    exit 1
fi

if ! command -v rclone &>/dev/null; then
    echo "Error: rclone is not installed" >&2
    exit 1
fi

LOCAL_FILE="${1:?Usage: upload.sh <local-file> <remote-path>}"
REMOTE_PATH="${2:?Usage: upload.sh <local-file> <remote-path>}"

rclone copyto "$LOCAL_FILE" "${RCLONE_REMOTE}:${RCLONE_BUCKET}/${REMOTE_PATH}" \
    --header-upload "Content-Type: text/html; charset=utf-8"

echo "${S3_PUBLIC_URL}/${REMOTE_PATH}"
