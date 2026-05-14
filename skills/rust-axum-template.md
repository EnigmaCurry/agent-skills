# Rust Axum Template

Create a new Rust Axum project from the template.

## Usage

`/rust-axum-template [project_name] [git_forge=DOMAIN] [git_username=USER]`

Arguments can be passed positionally or as `key=value` pairs:
- `project_name` (positional or `project_name=foo`) — the new project name
- `git_forge` — git forge domain (default: `github.com`)
- `git_username` — git forge username or org name

Example: `/rust-axum-template my-app git_username=acme`

## Steps

### 1. Check prerequisites and enter nix-shell

First, check if `nix-shell` is available on `$PATH`. If it is, **all commands in subsequent steps must be run inside nix-shell**. Use `nix-shell --run "<command>"` for every bash invocation (after the repo is cloned and `shell.nix` is available), or prefix multi-step work with a single `nix-shell` entry. The `shell.nix` in the template provides all required tools and sets up `OPENSSL_DIR`/`OPENSSL_LIB_DIR` automatically. Do NOT attempt to install individual packages via `nix profile install` — use `nix-shell` instead.

If `nix-shell` is not available, verify these tools are on `$PATH` manually:

| Tool | Notes |
|------|-------|
| `cargo` | Install via `rustup`; then run `rustup default stable` |
| `node` | Required by frontend build (vite/svelte-kit) |
| `pnpm` | Node package manager |
| `just` | Command runner |
| `envsubst` | Must be GNU gettext envsubst (not the Go a8m/envsubst) |
| `cargo-binstall` | Prebuilt binary installer |
| `pkg-config` | Needed if cargo builds native deps from source |
| `openssl` | Needed if cargo builds native deps from source |

Do not proceed until all required tools are available.

### 2. Set up Rust toolchain

If not using `nix-shell` (which handles this automatically), ensure a default Rust toolchain is configured:

```bash
rustup default stable
```

### 3. Get the project name

Parse `$ARGUMENTS` for `project_name`, `git_forge`, and `git_username` (positional or `key=value`).

If the project name is still empty, use AskUserQuestion to ask:
- Provide a suggested default (e.g., `"my-app"`) as the first option
- Let the user pick or enter a custom name via "Other"

### 4. Clone the template

Clone into the current working directory:

```bash
git clone https://github.com/EnigmaCurry/rust-axum-template "$PROJECT_NAME"
```

If the directory already exists, stop and tell the user.

### 5. Instantiate the project

Change into the new project directory and look for setup instructions:

1. If a `/create` skill is available in the cloned repo (check `.claude/skills/` or `.claude/commands/`), invoke it, passing the parsed arguments (`project_name`, `git_forge`, `git_username`).
2. Otherwise, read the project's `CLAUDE.md` and follow its instructions to instantiate the template with the chosen project name.

When running `setup.sh`, set `DEPS_TARGET=bin-deps` to prefer prebuilt binaries. Note: `bin-deps` is best-effort — `cargo-binstall` may fall back to source compilation for some packages (e.g., `sqlx-cli`), which requires `pkg-config` and `openssl` headers.

### 6. Verify success

After setup completes, run:

```bash
just test
```

Expect output containing test results with all tests passing. If tests fail, diagnose and fix before reporting success.

Report what was done when finished.
