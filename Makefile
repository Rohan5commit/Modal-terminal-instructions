PYTHON := /usr/bin/python3
MODAL := $(PYTHON) -m modal

.PHONY: setup auth heavy heavy-modal heavy-local usage-reset usage-show cmd shims-install shims-activate shell-bootstrap doctor agent-runner-install agent-runner-check antigravity-policy-install antigravity-policy-check

setup:
	$(PYTHON) -m pip install --user modal

auth:
	$(MODAL) setup

heavy:
	@if [ -z "$(PAYLOAD)" ]; then echo "Usage: make heavy PAYLOAD='{\"iterations\":24000000,\"workers\":6}'"; exit 2; fi
	$(MODAL) run primary_compute.py --payload '$(PAYLOAD)' --mode auto

heavy-modal:
	@if [ -z "$(PAYLOAD)" ]; then echo "Usage: make heavy-modal PAYLOAD='{\"iterations\":24000000,\"workers\":6}'"; exit 2; fi
	$(MODAL) run primary_compute.py --payload '$(PAYLOAD)' --mode modal

heavy-local:
	@if [ -z "$(PAYLOAD)" ]; then echo "Usage: make heavy-local PAYLOAD='{\"iterations\":24000000,\"workers\":6}'"; exit 2; fi
	$(MODAL) run primary_compute.py --payload '$(PAYLOAD)' --mode local

usage-show:
	$(MODAL) run primary_compute.py --show-state 1

usage-reset:
	@rm -f "$$HOME/.primary_compute_modal_usage.json"
	@echo "Reset $$HOME/.primary_compute_modal_usage.json"

cmd:
	@if [ -z "$(CMD)" ]; then echo "Usage: make cmd CMD='your command'"; exit 2; fi
	./scripts/modal_exec.sh -c "$(CMD)"

shims-install:
	./scripts/install_modal_shims.sh

shims-activate:
	@echo "Run: source ./scripts/activate_modal_only.sh"

shell-bootstrap:
	./scripts/bootstrap_modal_shell.sh

doctor:
	/bin/zsh -lc 'cd "$(PWD)"; echo "hostname cmd: $$(whence -p hostname)"; echo "python3 cmd: $$(whence -p python3)"; echo "/bin/hostname resolver: $$(whence -w /bin/hostname 2>/dev/null || true)"; echo "/usr/bin/python3 resolver: $$(whence -w /usr/bin/python3 2>/dev/null || true)"; echo "MODAL_SHIMS_ACTIVE=$${MODAL_SHIMS_ACTIVE:-unset}"; MODAL_RUN_FLAGS="" hostname; MODAL_RUN_FLAGS="" /bin/hostname; MODAL_RUN_FLAGS="" python3 -c "import platform, os; print(platform.platform()); print(os.getenv(\"IN_MODAL_TASK_RUNNER\"))"; MODAL_RUN_FLAGS="" /usr/bin/python3 -c "import platform, os; print(platform.platform()); print(os.getenv(\"IN_MODAL_TASK_RUNNER\"))"'

agent-runner-install:
	./scripts/install_agent_runner.sh

agent-runner-check:
	"$$HOME/.local/bin/modal-agent-runner" -c 'hostname && python3 -c "import platform, os; print(platform.system()); print(os.getenv(\"IN_MODAL_TASK_RUNNER\"))"'

antigravity-policy-install:
	./scripts/install_antigravity_policy.sh

antigravity-policy-check:
	./scripts/check_antigravity_policy.sh
