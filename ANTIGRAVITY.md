# Antigravity Unified Modal Policy

This is the canonical shared policy for all terminal-capable agents in this workspace.
Applies to Codex, Gemini Code Assist, Cline, Kilo Code, Roo Code, Claude Code, and similar agents.

## Mandatory Terminal Execution Path

All executable terminal commands must run through:

```bash
$HOME/.local/bin/modal-agent-runner -c "<raw command string>"
```

or

```bash
$HOME/.local/bin/modal-agent-runner -- <binary> <arg1> <arg2>
```

The runner forwards commands to `scripts/modal_exec.sh`, which executes them in Modal via `modal_tasks.py`.

## Agent-Specific Rule Files

- `AGENTS.md` mirrors this file for Codex/Kilo/Roo/Claude-style agents.
- `.rules/antigravity.rules` and `.rules/codex.rules` point to this policy for Codex rules loading.
- `.clinerules` mirrors this file for Cline.
- `.vscode/settings.json` defines `geminicodeassist.rules` for Gemini Code Assist.
- `.gemini/bin/bash` and `.gemini/.env` force Gemini `bash -c` shell invocations through `modal-agent-runner`.

## Prohibited Direct Local Execution

Do not run local direct commands such as:

- `ls`, `cat`, `find`, `rg`
- `python`, `python3`, `pip`, `uv`
- `node`, `npm`, `pnpm`, `yarn`
- `pytest`, `ruff`, `mypy`, `make`, `bash`, `zsh`

unless they are inside the Modal execution path above.

## Expected Local-Only Boundaries

Some operations are not terminal compute and remain local by design:

- UI rendering and editor interactions
- shell builtins (`cd`, `export`, `alias`)
- source-control operations (`git ...`)
- Modal control-plane submission command itself (`python3 -m modal ...`)
- network/chat inference performed by the provider backend

## Verification

Run:

```bash
make antigravity-policy-check
```

Successful routing should show:

- `hostname` prints `modal`
- `IN_MODAL_TASK_RUNNER=1`
