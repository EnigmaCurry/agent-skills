# Share Conversation

Export the current Claude Code conversation as a styled HTML page, upload it to an S3-compatible bucket, and return the public URL.

This skill has companion scripts in the same directory:
- `export.py` — converts JSONL session transcript to styled HTML
- `upload.sh` — uploads a file to S3 via rclone and prints the public URL

Resolve the skill directory by following the symlink: `readlink -f ~/.claude/commands` gives the skills root. The scripts are at `<skills-root>/share/export.py` and `<skills-root>/share/upload.sh`.

## Steps

### 1. Check prerequisites and load config

Verify `rclone` and `python3` are installed. If not, tell the user what to install and stop.

Check if `~/.config/claude-skills/export/config.env` exists. If it does, proceed to step 2.

If the config file does NOT exist, run the setup flow:

#### Setup flow

**a)** Run `rclone listremotes` to check for existing remotes.

**b)** Ask the user (using AskUserQuestion) whether to use an existing remote or create a new one.

**c)** If creating a new remote, ask the user for:
- Remote name (default: `claude-export`)
- S3 provider (AWS, Cloudflare R2, Minio, Backblaze B2, DigitalOcean Spaces, Other)
- Endpoint URL (skip for AWS)
- Access Key ID
- Secret Access Key
- Region (if applicable)

Create the remote with `rclone config create`. Always include `no_check_bucket=true` and `acl=public-read`:
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

**d)** Ask the user for the bucket name and public base URL (no trailing slash).

**e)** Write `~/.config/claude-skills/export/config.env` (mkdir -p first):
```bash
RCLONE_REMOTE=<remote-name>
RCLONE_BUCKET=<bucket>
S3_PUBLIC_URL=<public-url>
```

### 2. Ask for a title

Get a suggested title from the first user message:
```bash
SKILL_DIR="$(readlink -f ~/.claude/commands)/share"
python3 "${SKILL_DIR}/export.py" --cwd "$(pwd)" --first-message
```

From that message, suggest a short (3-5 word) title.

Use AskUserQuestion to show the suggested title and let the user confirm or provide an alternative. The user inputs a **title** (e.g. "Agent Skills Setup"), and you derive the kebab-case filename from it (e.g. `agent-skills-setup.html`).

### 3. Generate the HTML

Pass the title explicitly via `--title`:
```bash
python3 "${SKILL_DIR}/export.py" --cwd "$(pwd)" --title "${TITLE}" -o "/tmp/${FILENAME}"
```

### 4. Upload and return URL

Generate an 8-character random alphanumeric directory name and upload:
```bash
RANDOM_DIR=$(head -c 32 /dev/urandom | base64 | tr -dc 'a-z0-9' | head -c 8)
URL=$(bash "${SKILL_DIR}/upload.sh" "/tmp/${FILENAME}" "exports/${RANDOM_DIR}/${FILENAME}")
rm -f "/tmp/${FILENAME}"
```

Print the URL to the user.
