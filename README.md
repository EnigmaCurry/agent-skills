# agent-skills

Custom skills for [Claude Code](https://claude.ai/code) and
[OpenCode](https://opencode.ai).

Designed for use with the `claude` and `opencode` profiles from
[nixos-vm-template](https://github.com/EnigmaCurry/nixos-vm-template),
which provide a ready-made environment with all required dependencies
pre-installed.

## Install

### Claude Code: as a plugin

This repo is its own plugin marketplace, so no cloning or symlinking:

```bash
claude plugin marketplace add EnigmaCurry/agent-skills
claude plugin install agent-skills@enigmacurry
```

Or from inside a session: `/plugin marketplace add EnigmaCurry/agent-skills`,
then `/plugin install agent-skills@enigmacurry`.

The skills then answer to both `/share` and `/agent-skills:share`, and
`claude plugin details agent-skills` prints the component inventory and
the token cost (currently ~221 tokens always-on across the three).

To update an installed copy, `claude plugin update agent-skills`. That
only picks up a new `version` in `.claude-plugin/plugin.json`, so bump
it when publishing a change worth pushing out.

### OpenCode, or any other harness: symlink

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

Pick one method or the other. Installing the plugin *and* symlinking
`skills/` loads every skill twice.

## Skills

### /share

Export the current conversation as a styled HTML page, scan it for
secrets, and — after you approve — upload it to an S3-compatible bucket
via rclone and return a public URL. First run walks you through rclone
remote and bucket configuration. Never self-invoked, and the upload
itself is deliberately left out of `allowed-tools` so publishing always
prompts.

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
.claude-plugin/
  marketplace.json  # catalog; lists this repo as one plugin
  plugin.json       # plugin metadata (name, version, author)
skills/
  git-deploy/
    SKILL.md
  rust-axum-template/
    SKILL.md
  share/
    SKILL.md        # skill prompt
    export.py       # JSONL → HTML conversion
    upload.sh       # rclone upload
```

The repo root is both the marketplace and the single plugin it lists —
the entry's `source` is `"./"` — so `skills/` stays at the top level
and the symlink install keeps working unchanged. Validate any edit to
either manifest with `claude plugin validate ./ --strict`.

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
