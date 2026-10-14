---
name: share
description: Export this conversation as a styled HTML page, upload it to an S3-compatible bucket, and return a public URL.
disable-model-invocation: true
allowed-tools: Bash(rclone listremotes), Bash(python3 ${CLAUDE_SKILL_DIR}/export.py:*), Bash(bash ${CLAUDE_SKILL_DIR}/upload.sh:*), AskUserQuestion
---

Export the current conversation as a styled HTML page, upload it to an
S3-compatible bucket, and return the public URL.

Companion scripts live next to this file:

- `${CLAUDE_SKILL_DIR}/export.py` — transcript JSONL → styled HTML
- `${CLAUDE_SKILL_DIR}/upload.sh` — rclone upload, prints the public URL

## 1. Prerequisites and config

Check for `rclone` and `python3`. If `python3` is missing but `nix` is
available, use `nix run nixpkgs#python3 --` in place of `python3`
throughout. If `rclone` is missing, say so and stop.

If `~/.config/claude-skills/export/config.env` exists, go to step 2.
Otherwise run the setup flow:

**a)** `rclone listremotes` to see what already exists.

**b)** Ask with AskUserQuestion whether to use an existing remote or
create a new one.

**c)** For a new remote, collect: remote name (default
`claude-export`), S3 provider (AWS, Cloudflare R2, Minio, Backblaze B2,
DigitalOcean Spaces, Other), endpoint URL (skip for AWS), access key
id, secret access key, and region if applicable. Then:

```bash
rclone config create <name> s3 \
  provider=<provider> \
  access_key_id=<key> \
  secret_access_key=<secret> \
  endpoint=<endpoint> \
  region=<region> \
  no_check_bucket=true \
  acl=public-read
```

`acl=public-read` only does anything where object ACLs are still
honored. AWS disables ACLs by default on buckets created since 2023
("bucket owner enforced") and Cloudflare R2 ignores them entirely — on
those, public access comes from a bucket policy or an R2 public
development/custom domain, which the user must set up themselves. The
upload still succeeds; the URL just 403s until that is in place.

**d)** Ask for the bucket name and the public base URL (no trailing slash).

**e)** Write `~/.config/claude-skills/export/config.env` (`mkdir -p` first):

```bash
RCLONE_REMOTE=<remote-name>
RCLONE_BUCKET=<bucket>
S3_PUBLIC_URL=<public-url>
```

## 2. Pick a title

```bash
python3 "${CLAUDE_SKILL_DIR}/export.py" --cwd "$(pwd)" --first-message
```

Suggest a short (3–5 word) title from that message. Confirm it with
AskUserQuestion, letting the user override. Derive the filename from
the chosen title in kebab-case ("Agent Skills Setup" →
`agent-skills-setup.html`).

## 3. Generate the HTML

```bash
python3 "${CLAUDE_SKILL_DIR}/export.py" --cwd "$(pwd)" --title "${TITLE}" -o "/tmp/${FILENAME}"
```

## 4. Upload

```bash
RANDOM_DIR=$(head -c 32 /dev/urandom | base64 | tr -dc 'a-z0-9' | head -c 8)
URL=$(bash "${CLAUDE_SKILL_DIR}/upload.sh" "/tmp/${FILENAME}" "exports/${RANDOM_DIR}/${FILENAME}")
rm -f "/tmp/${FILENAME}"
```

Give the user the URL.
