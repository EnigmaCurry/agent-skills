# agent-skills

Custom Claude Code skills for global installation.

## Installation

Symlink the `skills/` directory to `~/.claude/commands`:

```bash
ln -s /path/to/agent-skills/skills ~/.claude/commands
```

## Structure

Skills live in the `skills/` directory as `.md` files. Each skill file
is a prompt that Claude Code loads when invoked via `/skill-name`.
