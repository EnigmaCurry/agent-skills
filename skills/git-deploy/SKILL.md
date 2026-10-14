---
name: git-deploy
description: Clone a git repository over SSH using a per-repo deploy key, via the `git deploy` extension. Use when a clone should authenticate with its own deploy key instead of a personal SSH key, or when the user asks to clone a repo with a deploy key.
arguments: [repo]
allowed-tools: Bash(command -v git-deploy), Bash(git-deploy:*), Bash(ssh:*), AskUserQuestion
---

Clone `$repo` with deploy key authentication via `git deploy`.

## Resolve the repository URL

`git deploy` accepts only full URLs or local paths — it does **not**
accept `org/repo` shorthand. Expand `$repo` before passing it on:

- **Bare name** (no `/`, no protocol) → `https://github.com/EnigmaCurry/<name>`
- **org/repo** → `https://github.com/<org>/<repo>`
- **Full URL** (`https://`, `git@`, `ssh://`) → unchanged

If `$repo` is empty, ask the user for the repository with AskUserQuestion.

## Locate git-deploy

Try `command -v git-deploy`, then `~/bin/git-deploy`. If neither
exists, tell the user it is not installed and link
https://blog.rymcg.tech/blog/linux/git-extensions/ — then stop.

Store the resolved path as `GIT_DEPLOY`.

## Run it

The script writes status messages to stderr and the public key block to
stdout. Capture them separately; interleaved streams make the key block
unparseable:

```bash
OUT=$(mktemp -t git-deploy-out.XXXXXX); ERR=$(mktemp -t git-deploy-err.XXXXXX)
"$GIT_DEPLOY" <REPO_URL> >"$OUT" 2>"$ERR"; echo "EXIT:$?"
```

Read `$OUT` (public key) and `$ERR` (status/progress) separately.

## Handle the result

### Success (exit 0)

The repo was cloned or was already configured. The destination is
`~/git/vendor/{org}/{repo}` with **org lowercased** by the script
(`EnigmaCurry` → `enigmacurry`). Read the real path from the stderr
output (the `Location:` line) rather than reconstructing it.

### Exit 1 — deploy key not yet authorized

Stdout holds a public key block (`ssh-ed25519 ...`). Then:

1. Show the public key from `$OUT`.
2. Build the deploy-key settings URL from the host, org, and repo:
   - **GitHub** (`github.com`): `https://github.com/{org}/{repo}/settings/keys`
   - **GitLab** (`gitlab.com`, or any host containing `gitlab`):
     `https://{host}/{org}/{repo}/-/settings/repository` (Deploy Keys section)
   - **Forgejo/Gitea** (anything else): `https://{host}/{org}/{repo}/settings/keys`
3. Tell the user to add the key there. For GitHub, remind them to
   **check "Allow write access"** if they need to push.
4. Ask with AskUserQuestion whether they have added it.
5. Once confirmed, **seed the SSH host key before re-running**. Take the
   SSH alias from the stderr output (it looks like
   `deploy--github.com--org-repo`) and run:
   ```bash
   ssh -o StrictHostKeyChecking=accept-new -T <alias> 2>&1 || true
   ```
   Without this the re-run fails silently, because the alias hostname
   is not in `known_hosts` yet.
6. Re-run `git deploy` the same way and report the result.

### Re-run still reports NOT YET AUTHORIZED

Diagnose before asking the user to re-add the key:

1. `ssh -T <alias> 2>&1`
2. If SSH authenticates, the deploy key is fine and this is a host-key
   or config problem — show the SSH output and the alias block from
   `~/.ssh/config`.
3. If SSH says "Permission denied", the key really is not authorized.
   Ask the user to confirm they added it to the right repository.

### Other failures

Report the error output as-is.
