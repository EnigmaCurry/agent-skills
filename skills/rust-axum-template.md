# Rust Axum Template

Create a new Rust Axum project from the template.

## Usage

`/rust-axum-template [project]` — the argument is the new project name.

## Steps

### 1. Check prerequisites

Verify the following tools are available on `$PATH`:

| Tool | Nix package |
|------|-------------|
| `cargo` | `nixpkgs#rustup` (then `rustup default stable`) |
| `pnpm` | `nixpkgs#pnpm` |
| `just` | `nixpkgs#just` |
| `envsubst` | `nixpkgs#envsubst` |
| `cargo-binstall` | `nixpkgs#cargo-binstall` |

If any are missing, list the missing tools and ask the user whether to install them via `nix profile install`. Do not proceed until all are available.

### 2. Get the project name

If `$ARGUMENTS` is empty or blank, use AskUserQuestion to ask the user for the new project name.

### 3. Clone the template

Clone into the current working directory:

```bash
git clone https://github.com/EnigmaCurry/rust-axum-template "$PROJECT_NAME"
```

If the directory already exists, stop and tell the user.

### 4. Instantiate the project

Change into the new project directory and look for setup instructions:

1. If a `/create` skill is available in the cloned repo (check for a `create.md` in `.claude/commands/` or similar), invoke it. When running `setup.sh`, set `DEPS_TARGET=bin-deps` so that prebuilt binaries are downloaded instead of compiling dependencies from source.
2. Otherwise, read the project's `CLAUDE.md` and follow its instructions to instantiate the template with the chosen project name. When running `setup.sh`, set `DEPS_TARGET=bin-deps`.

Report what was done when finished.
