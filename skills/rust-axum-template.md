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

### 1. Check prerequisites

Verify the following tools are available on `$PATH`:

| Tool | Nix package | Notes |
|------|-------------|-------|
| `cargo` | `nixpkgs#rustup` | Rust toolchain manager |
| `node` | `nixpkgs#nodejs` | Required by frontend build (vite/svelte-kit) |
| `pnpm` | `nixpkgs#pnpm` | Node package manager |
| `just` | `nixpkgs#just` | Command runner |
| `envsubst` | `nixpkgs#envsubst` | Template variable substitution |
| `cargo-binstall` | `nixpkgs#cargo-binstall` | Prebuilt binary installer |
| `pkg-config` | `nixpkgs#pkg-config` | Needed if cargo builds native deps from source |
| `openssl` | `nixpkgs#openssl.dev` | Needed if cargo builds native deps from source |

If any are missing, list the missing tools and offer two installation methods:
- **Preferred (Nix shell):** If the cloned repo contains a `shell.nix`, suggest `nix-shell` or `direnv allow` to enter a reproducible dev environment.
- **Fallback (Nix profile):** `nix profile install <package>`. Note: this may conflict with home-manager managed profiles — if so, prefer `nix-shell -p <packages>` instead.

Do not proceed until all required tools are available.

### 2. Set up Rust toolchain

Ensure a default Rust toolchain is configured:

```bash
rustup default stable
```

This is required before any `cargo` command will work. Do not skip this step.

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
