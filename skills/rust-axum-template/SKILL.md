---
name: rust-axum-template
description: Create a new Rust Axum project from EnigmaCurry/rust-axum-template — clone it, instantiate the template, and verify the build passes. Use when starting a new Rust web service from this template.
arguments: [project_name, git_forge, git_username]
allowed-tools: Bash(git clone:*), Bash(nix-shell:*), Bash(rustup:*), Bash(just:*), Bash(cargo:*), AskUserQuestion
---

Create a new Rust Axum project from the template.

Arguments: `$project_name` (the new project), `$git_forge` (forge
domain, default `github.com`), `$git_username` (forge user or org).

## 1. Settle the project name

If `$project_name` is empty, ask with AskUserQuestion, offering a
sensible default (e.g. `my-app`) as the first option.

## 2. Clone the template

Into the current working directory:

```bash
git clone https://github.com/EnigmaCurry/rust-axum-template "$project_name"
```

If the directory already exists, stop and tell the user.

## 3. Prefer nix-shell for everything that follows

Check whether `nix-shell` is on `$PATH`. If it is, **every command from
here on runs inside it** — use `nix-shell --run "<command>"` per
invocation, or enter `nix-shell` once for a run of work. The template's
`shell.nix` provides all required tools and sets `OPENSSL_DIR` /
`OPENSSL_LIB_DIR` for you. Do **not** install individual packages with
`nix profile install`.

If `nix-shell` is unavailable, verify these are on `$PATH` and do not
proceed until they all are:

| Tool | Notes |
|------|-------|
| `cargo` | Install via `rustup`, then `rustup default stable` |
| `node` | Required by the frontend build (vite/svelte-kit) |
| `pnpm` | Node package manager |
| `just` | Command runner |
| `envsubst` | Must be GNU gettext envsubst, **not** the Go a8m/envsubst |
| `cargo-binstall` | Prebuilt binary installer |
| `pkg-config` | Needed when cargo builds native deps from source |
| `openssl` | Needed when cargo builds native deps from source |

Without `nix-shell`, also make sure a default toolchain is set:

```bash
rustup default stable
```

## 4. Instantiate the project

Change into the new directory and look for its own setup entry point:

1. If the cloned repo ships a `/create` skill (check `.claude/skills/`
   or `.claude/commands/`), invoke it with `$project_name`,
   `$git_forge`, and `$git_username`.
2. Otherwise read the project's `CLAUDE.md` and follow it.

When running `setup.sh`, set `DEPS_TARGET=bin-deps` to prefer prebuilt
binaries. This is best-effort: `cargo-binstall` still falls back to
source builds for some crates (e.g. `sqlx-cli`), which is why
`pkg-config` and the openssl headers matter above.

## 5. Verify

```bash
just test
```

All tests must pass. If any fail, diagnose and fix before reporting
success. Then summarize what was created and where.
