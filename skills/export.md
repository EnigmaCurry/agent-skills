# Export Conversation to S3

Export the current Claude Code conversation as a styled HTML page, upload it to an S3-compatible bucket with a random directory path and descriptive filename, and return the public URL.

## Configuration

The skill config lives at `~/.config/claude-skills/export/config.env`:

```bash
RCLONE_REMOTE=myremote           # rclone remote name
RCLONE_BUCKET=my-bucket-name     # bucket name on the remote
S3_PUBLIC_URL=https://example.com # base URL for public access (no trailing slash)
```

## Steps

### 1. Check prerequisites and load config

Verify `rclone` is installed. If not, tell the user to install it and stop.

Check if `~/.config/claude-skills/export/config.env` exists. If it does, source the variables and proceed to step 2.

If the config file does NOT exist, run the setup flow:

#### Setup flow

**a) Check for existing rclone remotes:**

Run `rclone listremotes` to see if any S3-compatible remotes already exist.

**b) Ask the user** (using AskUserQuestion) whether to use an existing remote or create a new one.

**c) If creating a new remote**, ask the user for:
- Remote name (default: `claude-export`)
- S3 provider (AWS, Cloudflare R2, Minio, Backblaze B2, DigitalOcean Spaces, Other)
- Endpoint URL (skip for AWS)
- Access Key ID
- Secret Access Key
- Region (if applicable)

Then create the remote using `rclone config create`:
```bash
rclone config create <name> s3 \
  provider=<provider> \
  access_key_id=<key> \
  secret_access_key=<secret> \
  endpoint=<endpoint> \
  region=<region>
```

**d) Ask the user for:**
- Bucket name
- Public base URL for the bucket (how the bucket is accessed via HTTP)

**e) Write the config file** (mkdir -p the directory first):
```bash
RCLONE_REMOTE=<remote-name>
RCLONE_BUCKET=<bucket>
S3_PUBLIC_URL=<public-url>
```

### 2. Find the current session transcript

The current session JSONL file is in `~/.claude/projects/`. Determine the project directory by sanitizing the current working directory (replace `/` with `-`, prepend `-`). Then find the most recently modified `.jsonl` file in that directory. That is the current session.

### 3. Parse the JSONL and build HTML

Read the JSONL file and extract the conversation. Process each line as JSON:

- **`type: "user"`** — The user's message is in `.message.content` (string or array of content blocks). If it's a string, render it directly. If it's an array, look for `type: "text"` blocks for display text, and `type: "tool_result"` blocks (skip these — they're tool responses already shown in assistant context).
- **`type: "assistant"`** — The assistant's message is in `.message.content` (array of content blocks):
  - `type: "text"` — Render as markdown (convert to HTML with code highlighting)
  - `type: "tool_use"` — Show as a collapsible details block with the tool name as summary and the input as formatted JSON/code
  - `type: "thinking"` — Skip (don't include thinking blocks)
- **Skip** lines with type: `permission-mode`, `file-history-snapshot`, `system`, `attachment`, `last-prompt`

Filter out system-reminder tags and their content from all rendered text — these are internal and should not appear in the export. Specifically, strip anything matching `<system-reminder>...</system-reminder>` including the tags and everything between them.

Also filter out `<local-command-caveat>...</local-command-caveat>` tags and content.

### 4. Generate the HTML

Write a self-contained HTML file (all CSS inline, no external dependencies) with:

**Page layout:**
- Max-width ~900px, centered, clean sans-serif font (system font stack)
- Light background (#f8f9fa), subtle card-style message blocks

**User messages:**
- Right-aligned or distinguished with a colored left border (blue, #2563eb)
- Label: "User"
- White background card with subtle shadow

**Assistant messages:**
- Left-aligned or distinguished with a different colored left border (green, #059669)
- Label: "Assistant"
- White background card with subtle shadow

**Code blocks:**
- Dark background (#1e1e2e), light text (#cdd6f4)
- Monospace font, horizontal scroll for overflow
- Language label if present
- Syntax classes for basic highlighting (keywords, strings, comments)

**Diff blocks (```diff):**
- Lines starting with `+` in green (#a6e3a1) background
- Lines starting with `-` in red (#f38ba8) background
- Lines starting with `@@` in purple (#cba6f7)
- Dark background like code blocks

**Tool use blocks:**
- Collapsible `<details>` element
- Summary shows tool name with a wrench icon
- Body shows the tool input as formatted code
- Muted styling (gray border, smaller text)

**Header:**
- Title: "Claude Code Conversation"
- Subtitle: date and project directory
- Thin colored accent bar at top

**Footer:**
- "Exported from Claude Code" with timestamp

### 5. Generate filename and confirm

Auto-generate a descriptive filename based on the first user message or conversation topic. Keep it short (3-5 words), kebab-case, ending in `.html`. Examples: `nixos-vm-setup.html`, `s3-export-skill.html`.

Use AskUserQuestion to show the generated name and let the user confirm or provide an alternative.

### 6. Generate random path and upload

Generate an 8-character random alphanumeric directory name. The full S3 key will be: `exports/<random>/<filename>`

Upload using rclone:
```bash
rclone copyto /tmp/claude-export.html "${RCLONE_REMOTE}:${RCLONE_BUCKET}/exports/${RANDOM_DIR}/${FILENAME}" \
  --header-upload "Content-Type: text/html; charset=utf-8"
```

### 7. Return the URL

Print the full public URL: `${S3_PUBLIC_URL}/exports/${RANDOM_DIR}/${FILENAME}`

## Important notes

- The HTML must be fully self-contained — no CDN links, no external CSS/JS
- Use a Python or Node.js script (whichever is available) to parse the JSONL and generate HTML, rather than trying to do it all in bash/jq
- Convert markdown in messages to HTML (headings, bold, italic, lists, links, code blocks)
- The script should handle large conversations gracefully
- Clean up temp files after upload
