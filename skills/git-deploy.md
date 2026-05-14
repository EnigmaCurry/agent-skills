# Git Deploy

Clone a git repository with deploy key authentication via `git deploy`.

## Usage

`/git-deploy [REPO]` — the argument is a repository URL or shorthand name.

## Argument parsing

`$ARGUMENTS` is the repo reference. It can be any format that `git deploy` accepts (full URLs, `org/repo`, etc.), plus one convenience shorthand:

- If `$ARGUMENTS` is a **bare name with no `/` and no protocol prefix**, prepend `EnigmaCurry/` to make it `https://github.com/EnigmaCurry/$ARGUMENTS`.
- Otherwise, pass `$ARGUMENTS` through to `git deploy` unchanged — it already handles all URL formats and normalization.

If `$ARGUMENTS` is empty or blank, use AskUserQuestion to ask the user for the repository.

## Locate git-deploy

Before running, find the `git-deploy` executable. Try in order:

1. `command -v git-deploy` (user's PATH)
2. `~/bin/git-deploy` (default install location)

If neither exists, tell the user that `git-deploy` is not installed
and link them to the blog post:
https://blog.rymcg.tech/blog/linux/git-extensions/

Store the resolved path as `GIT_DEPLOY`.

## Run git deploy

The script writes status messages to stderr and the public key block
to stdout. Capture them separately to avoid stream-interleaving issues
in the Bash tool:

```
$GIT_DEPLOY <REPO_ARG> >/tmp/git-deploy-out 2>/tmp/git-deploy-err; echo "EXIT:$?"
```

Then read `/tmp/git-deploy-out` (public key) and `/tmp/git-deploy-err`
(status/progress) separately.

## Handle the result

### Success (exit code 0)

The repo was cloned or already configured. Report the clone location to the user.

### Failure (exit code 1) — deploy key not yet authorized

The stdout output will contain a public key block (`ssh-ed25519 ...`).
When this happens:

1. Extract and display the public key from `/tmp/git-deploy-out`.
2. Parse the host, org, and repo from the URL. Build the appropriate deploy keys settings URL based on the host:
   - **GitHub** (`github.com`): `https://github.com/{org}/{repo}/settings/keys`
   - **GitLab** (`gitlab.com` or any host with `gitlab` in the name): `https://{host}/{org}/{repo}/-/settings/repository` (Deploy Keys section)
   - **Forgejo/Gitea** (any other host): `https://{host}/{org}/{repo}/settings/keys`
3. Tell the user to add the deploy key to the repository. Provide the settings URL. For GitHub, remind them to **check "Allow write access"** if they need push capability.
4. Ask the user (using AskUserQuestion) whether they have added the key.
5. Once confirmed, **seed the SSH host key** before re-running. Parse
   the SSH alias from the stderr output (it looks like
   `deploy--github.com--org-repo`) and run:
   ```
   ssh -o StrictHostKeyChecking=accept-new -T <alias> 2>&1 || true
   ```
   This prevents the re-run from failing silently because the alias
   hostname isn't yet in `known_hosts`.
6. Re-run `$GIT_DEPLOY <REPO_ARG>` (same stdout/stderr split) and
   report the result.

### Re-run still fails

If the re-run reports "NOT YET AUTHORIZED" again after the user
confirmed they added the key, diagnose before asking the user to
re-add:

1. Test SSH directly: `ssh -T <alias> 2>&1`
2. If SSH succeeds ("successfully authenticated" or similar), the
   deploy key is fine — it is a host-key or config issue. Show the
   SSH output and the contents of the alias block from `~/.ssh/config`
   to help debug.
3. If SSH fails with "Permission denied", the key genuinely isn't
   authorized. Ask the user to double-check the key was added to the
   correct repository.

### Other failures

If the command fails for a reason other than an unauthorized deploy key, report the error output to the user.
