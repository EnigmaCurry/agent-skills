# agent-skills

Custom slash command skills for [Claude Code](https://claude.ai/code) and [OpenCode](https://opencode.ai).

## Installation

Symlink the `skills/` directory to `~/.claude/commands`:

```bash
ln -s /path/to/agent-skills/skills ~/.claude/commands
```

## Skills

### /share

Export the current conversation as a styled HTML page, upload it to an
S3-compatible bucket via rclone, and return a public URL. First run
walks you through rclone remote and bucket configuration.

### /rust-axum-template

Clone the [rust-axum-template](https://github.com/EnigmaCurry/rust-axum-template)
and instantiate it as a new project. Usage: `/rust-axum-template my-app`

## Structure

Each skill is either a single `.md` file or a directory under `skills/`:

```
skills/
  share/
    share.md      # skill prompt
    export.py     # JSONL → HTML conversion
    upload.sh     # rclone upload
```

Skill `.md` files are prompts loaded when invoked via `/skill-name`.
Supporting scripts and utilities live alongside the prompt in the same
directory.
