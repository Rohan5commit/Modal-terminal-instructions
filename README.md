# Modal Offload Toolkit

This repo now has two layers:

1. `primary_compute.py`: step-by-step heavy compute offload with 6 cores / 14 GiB and daily budget tracking.
2. `modal_tasks.py` + shell shims: offload as many CLI commands as possible to Modal.

## 1) Setup once

```bash
make setup
make auth
```

## 2) Heavy function in Modal

`primary_compute.py` defines:

- `heavy_task(payload)` running in Modal with:
  - `cpu=6`
  - `memory=14 * 1024` MiB
- `do_heavy_stuff(payload)` as the expensive CPU logic

The function resource config is pinned by:

```python
CPU_CORES = 6
MEMORY_MB = 14 * 1024
```

## 3) Modal usage budget tracking

Local state file:

- `~/.primary_compute_modal_usage.json`

Tracked values:

- `day` (YYYY-MM-DD)
- `used_min` (Modal runtime minutes measured locally)

Default budget:

- `MAX_MIN_PER_DAY = 180` (3 hours/day)

Override with env var:

```bash
export PRIMARY_MODAL_MAX_MIN_PER_DAY=120
```

## 4) Run modes

Auto mode (recommended): Modal until daily budget is reached.

```bash
make heavy PAYLOAD='{"iterations":24000000,"workers":6}'
```

Force Modal:

```bash
make heavy-modal PAYLOAD='{"iterations":24000000,"workers":6}'
```

Force local:

```bash
make heavy-local PAYLOAD='{"iterations":24000000,"workers":6}'
```

Show tracked usage:

```bash
make usage-show
```

Reset tracked usage:

```bash
make usage-reset
```

## 5) Payload knobs

- `iterations`: total compute loop count
- `workers`: parallel worker processes (`6` recommended for this setup)
- `salt`: checksum variation integer

Example:

```bash
make heavy PAYLOAD='{"iterations":30000000,"workers":6,"salt":23}'
```

## Notes

- This offloads CPU-heavy tasks well (backtests, pipelines, heavy notebook cells).
- macOS UI apps (Safari, Finder, TradingView, TWS UI) still run locally by design.
- Keep expensive logic inside `do_heavy_stuff(...)` and always call via `run_heavy(...)`.

## CLI Offload (any command that can run in Modal)

Run directly through the command gateway:

```bash
./scripts/modal_exec.sh -- <command> [args...]
./scripts/modal_exec.sh -c "<shell command>"
```

Examples:

```bash
./scripts/modal_exec.sh -- rg "TODO" .
./scripts/modal_exec.sh -- python -m pytest -q
./scripts/modal_exec.sh --no-sync-back -- cat README.md
```

Enable strict auto-routing shims:

```bash
./scripts/install_modal_shims.sh
source ./scripts/activate_modal_only.sh
```

After activation, most executable commands are automatically forwarded to Modal.
Expected local-only exceptions are GUI/UI apps, shell builtins, `git`, and Modal control-plane commands.

## Agent terminal-runner enforcement (Kilo, Gemini, Claude, Roo, Cline, Antigravity, Codex)

Install a global terminal runner once:

```bash
make agent-runner-install
```

This creates:

```bash
$HOME/.local/bin/modal-agent-runner
```

Point each agent's terminal tool/command runner to that binary.
It forwards terminal commands to `scripts/modal_exec.sh`, so command execution is Modal-backed.
Model chat/inference stays on the agent provider side; this enforces terminal command execution only.

Command templates:

```bash
$HOME/.local/bin/modal-agent-runner -c "<raw command string>"
$HOME/.local/bin/modal-agent-runner -- <binary> <args...>
```

Quick verification:

```bash
make agent-runner-check
```

## Antigravity one-file policy

Canonical policy file:

```bash
ANTIGRAVITY.md
```

Install workspace + Antigravity user-level policy wiring:

```bash
make antigravity-policy-install
```

This installs:

- workspace `AGENTS.md` mirror from `ANTIGRAVITY.md`
- workspace `.clinerules` mirror from `ANTIGRAVITY.md` for Cline
- workspace `.rules/antigravity.rules` and `.rules/codex.rules` for Codex
- workspace `.vscode/settings.json` update for `geminicodeassist.rules` and `geminicodeassist.agentYoloMode=false`
- workspace Gemini hard-routing files:
  - `.gemini/bin/bash` (wraps `bash -c ...` to `modal-agent-runner`)
  - `.gemini/.env` (prepends `.gemini/bin` to `PATH`, sets `GEMINI_YOLO_MODE=false`)
- user files (when run outside Modal):
  - `~/Library/Application Support/Antigravity/User/ANTIGRAVITY.md`
  - `~/Library/Application Support/Antigravity/User/AGENTS.md` (symlink)
  - `~/Library/Application Support/Antigravity/User/CLAUDE.md` (symlink)
- Antigravity settings updates for Kilo/Roo/Claude plus Gemini rules and `geminicodeassist.agentYoloMode=false`

Check policy + routing:

```bash
make antigravity-policy-check
```

## Shell hardening fix

Some agents execute commands in non-interactive `zsh` without sourcing repo scripts.
Install repo-scoped shell bootstrap once:

```bash
make shell-bootstrap
```

This writes guarded blocks to `~/.zshenv`, `~/.zprofile`, `~/.zshrc`, `~/.bashrc`, and `~/.profile` so sessions that start in this repo automatically prepend `.modal-shims`.
For zsh, it also wraps common absolute binary paths (for example `/bin/ls` and `/usr/bin/python3`) to force Modal routing.

Run a verification for shell-level auto-routing:

```bash
make doctor
```
