# agent-skills

Custom skills for [Claude Code](https://claude.ai/code) and
[OpenCode](https://opencode.ai).

Designed for use with the `claude` and `opencode` profiles from
[nixos-vm-template](https://github.com/EnigmaCurry/nixos-vm-template),
which provide a ready-made environment with all required dependencies
pre-installed.

## Quickstart for AI agents

Paste the following prompt into a fresh agent session to bootstrap the
skills onto a new machine (customize as needed):

```
Clone and install my agent-skills. Clone the repo to
~/git/vendor/enigmacurry/agent-skills, then symlink the skills/
directory to the agent skills path (create parent dirs if needed).
If the repo or symlink already exists, skip that step. Print the
list of installed skills when done. Remind me to restart the
agent session so the new slash commands are loaded.

The skills path depends on the agent:

  Claude Code: ~/.claude/skills
  OpenCode:    ~/.config/opencode/skills
               (OpenCode also reads ~/.claude/skills, so one
                symlink there covers both agents)
  Generic:     Whatever skills dir the harness uses

git clone https://github.com/EnigmaCurry/agent-skills ~/git/vendor/enigmacurry/agent-skills
ln -sfn ~/git/vendor/enigmacurry/agent-skills/skills ~/.claude/skills
```

## Skills

### /share

Export the current conversation as a styled HTML page, upload it to an
S3-compatible bucket via rclone, and return a public URL. First run
walks you through rclone remote and bucket configuration. Never
self-invoked; you have to ask for it.

### /rust-axum-template

Clone the [rust-axum-template](https://github.com/EnigmaCurry/rust-axum-template)
and instantiate it as a new project. Usage: `/rust-axum-template my-app`

### /git-deploy

Clone a git repository with deploy key authentication. Wraps the
[git deploy](https://blog.rymcg.tech/blog/linux/git-extensions/#git-deploy)
command. Defaults bare repo names to the `EnigmaCurry` GitHub org.
Usage: `/git-deploy some-repo` or `/git-deploy https://github.com/user/repo`

## Structure

Each skill is a directory under `skills/` containing a `SKILL.md`, plus
any scripts it needs:

```
skills/
  git-deploy/
    SKILL.md
  rust-axum-template/
    SKILL.md
  share/
    SKILL.md      # skill prompt
    export.py     # JSONL → HTML conversion
    upload.sh     # rclone upload
```

`SKILL.md` opens with YAML frontmatter — `name` and `description` (how
the agent decides to invoke it), optional `arguments` for `$named`
substitution, `allowed-tools` to pre-approve the commands the skill
runs, and `disable-model-invocation: true` for skills that should only
ever run when you type them. The body is the prompt, loaded on
invocation. Scripts are referenced through `${CLAUDE_SKILL_DIR}`, which
expands to the skill's own directory.

Custom commands were merged into skills, so a flat
`~/.claude/commands/<name>.md` still works — but the directory form is
preferred, since it can bundle scripts and reference files that cost no
context until the skill runs.
