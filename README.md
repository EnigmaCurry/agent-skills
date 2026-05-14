# agent-skills

Custom Claude Code skills for global installation.

## Installation

Add to `~/.claude/settings.json`:

```json
{
  "skills": [
    "/home/user/git/vendor/enigmacurry/agent-skills/skills"
  ]
}
```

## Structure

Skills live in the `skills/` directory as `.md` files. Each skill file
is a prompt that Claude Code loads when the skill is invoked via
`/skill-name`.
