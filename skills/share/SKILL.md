---
name: share
description: Export this conversation as a styled HTML page, upload it to an S3-compatible bucket, and return a public URL.
disable-model-invocation: true
allowed-tools: Bash(rclone listremotes), Bash(rclone lsd:*), Bash(python3 ${CLAUDE_SKILL_DIR}/export.py:*), AskUserQuestion
---

Export the current conversation as a styled HTML page, upload it to an
S3-compatible bucket, and return the public URL.

**This publishes to a public URL.** The page renders tool inputs
verbatim — bash commands, written file contents, edit diffs — so
anything secret that passed through them ships with it. Never upload
before completing the review step below, and never upload without the
user's explicit go-ahead in this turn.

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

For an existing remote, check whether it has `no_check_bucket` — one
created outside this flow often lacks it, which breaks the upload in
step 5. Filter the output; `rclone config show` prints the access key
and secret in full, and there is no reason to put them in the
transcript:

```bash
rclone config show <name> | grep -E '^(no_check_bucket|acl)'
```

Fix it now rather than at upload time:

```bash
rclone config update <name> no_check_bucket=true acl=public-read
```

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

Write it somewhere local first — this is not the publish step:

```bash
python3 "${CLAUDE_SKILL_DIR}/export.py" --cwd "$(pwd)" --title "${TITLE}" -o "/tmp/${FILENAME}"
```

The transcript is cut at the `/share` invocation, so the page ends
where the user typed the command and never contains the steps of this
export. Any *earlier* `/share` run in the same thread collapses to a
short "Omitted" note, and export ids from previously published pages
are replaced with `REDACTED` wherever they still appear. Without that,
each export would republish the unguessable path of the one before it.

Report whichever of these the command prints — `truncated`, `omitted`,
`redacted export id(s)` — so the user knows what was dropped. It exits
non-zero and writes nothing if there is no conversation before the
invocation.

## 4. Review before publishing

Scan what the page would expose:

```bash
python3 "${CLAUDE_SKILL_DIR}/export.py" --cwd "$(pwd)" --scan
```

Findings print as `msg N (role) Tool: [kind] redacted-preview`, ending
in a `SCAN:` line. The scan covers message text and tool inputs, which
is exactly what the page renders.

Then:

- **If anything was found**, show every finding verbatim and treat
  publishing as blocked. Say which message and tool each came from so
  the user can judge it. Offer to delete the local file, or to publish
  anyway only if they look and tell you the hits are false positives.
  Do not characterize a finding as a false positive yourself.
- **If the scan is clean**, say so — and say plainly that it is pattern
  matching, not a guarantee: it will not catch an unrecognized
  credential format, a private hostname, an internal URL, or anything
  else the user would not want public.

Either way, give the user the local path (`/tmp/${FILENAME}`) so they
can open it, and tell them roughly what the export contains: every
message up to the `/share` command, every tool input, no tool output.

The redaction covers export ids in the `exports/<id>` form. It is not a
general privacy pass — bucket hostnames, local paths and usernames all
still render, and the scan does not flag them.

Then ask with AskUserQuestion whether to publish. Offer "Publish" and
"Don't publish — delete the file". Stop here if they decline, and
`rm -f "/tmp/${FILENAME}"`.

## 5. Upload

Only after an explicit yes:

```bash
RANDOM_DIR=$(head -c 32 /dev/urandom | base64 | tr -dc 'a-z0-9' | head -c 8)
URL=$(bash "${CLAUDE_SKILL_DIR}/upload.sh" "/tmp/${FILENAME}" "exports/${RANDOM_DIR}/${FILENAME}")
rm -f "/tmp/${FILENAME}"
```

Give the user the URL, and note that the random directory makes it
unguessable but not private — anyone with the link can read it, and it
may be cached or indexed even if deleted later.

### If the upload fails with `CreateBucket` / `AccessDenied`

```
Failed to copy: failed to prepare upload: operation error S3:
CreateBucket, https response error StatusCode: 403 ... AccessDenied
```

The remote is missing `no_check_bucket`, so rclone tries to create the
bucket before every upload and the key is not permitted to. The file
itself was never sent, and retrying verbatim fails identically. Confirm
the bucket is otherwise reachable, then set the flag and upload again:

```bash
rclone lsd <remote>:<bucket>                                    # exit 0 = credentials fine
rclone config update <remote> no_check_bucket=true acl=public-read
```

This is a persistent edit to the user's rclone config — say so when
reporting it.
