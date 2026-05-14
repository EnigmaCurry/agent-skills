# agent-skills

Custom slash command skills for [Claude Code](https://claude.ai/code) and [OpenCode](https://opencode.ai).

## Quickstart for AI agents

Paste the following prompt into a fresh agent session to bootstrap the
skills onto a new machine (customize as needed):

```
Clone and install my agent-skills. Clone the repo to
~/git/vendor/enigmacurry/agent-skills, then symlink the skills/
directory to the agent commands path (create parent dirs if needed).
If the repo or symlink already exists, skip that step. Print the
list of installed skills when done. Remind me to restart the
agent session so the new slash commands are loaded.

The commands path depends on the agent:

  Claude Code: ~/.claude/commands
  OpenCode:    ~/.opencode/commands
  Generic:     Whatever commands dir the harness uses

git clone https://github.com/EnigmaCurry/agent-skills ~/git/vendor/enigmacurry/agent-skills
ln -sfn ~/git/vendor/enigmacurry/agent-skills/skills ~/.claude/commands
```

## Skills

### /share

Export the current conversation as a styled HTML page, upload it to an
S3-compatible bucket via rclone, and return a public URL. First run
walks you through rclone remote and bucket configuration.

### /rust-axum-template

Clone the [rust-axum-template](https://github.com/EnigmaCurry/rust-axum-template)
and instantiate it as a new project. Usage: `/rust-axum-template my-app`

### /git-deploy

Clone a git repository with deploy key authentication. Wraps the
[git deploy](https://blog.rymcg.tech/blog/linux/git-extensions/#git-deploy)
command. Defaults bare repo names to the `EnigmaCurry` GitHub org.
Usage: `/git-deploy some-repo` or `/git-deploy https://github.com/user/repo`

## Structure

Each skill is either a single `.md` file or a directory under `skills/`:

```
skills/
  git-deploy.md   # single-file skill
  rust-axum-template.md
  share/
    share.md      # skill prompt
    export.py     # JSONL → HTML conversion
    upload.sh     # rclone upload
```

Skill `.md` files are prompts loaded when invoked via `/skill-name`.
Supporting scripts live alongside the prompt in the same directory.
