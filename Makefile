PROJECT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
WORKDIR ?= $(CURDIR)
ARGS ?=
BIN_DIR ?= $(HOME)/.local/bin
VENV_DIR := $(PROJECT_DIR)/.venv
VENV_PYTHON := $(VENV_DIR)/bin/python

.PHONY: start install-global uninstall-global

start:
	@python -m pip install -e "$(PROJECT_DIR)" --quiet
	@cd "$(WORKDIR)" && python -m git_disk_usage $(ARGS)

install-global:
	@if [ ! -x "$(VENV_PYTHON)" ] || ! "$(VENV_PYTHON)" -c 'import sys' >/dev/null 2>&1; then \
		python3 -m venv --clear "$(VENV_DIR)"; \
	fi
	@"$(VENV_PYTHON)" -m pip install -e "$(PROJECT_DIR)" --quiet
	@mkdir -p "$(BIN_DIR)"
	@ln -sf "$(VENV_DIR)/bin/git-disk-usage" "$(BIN_DIR)/git-disk-usage"
	@ln -sf "$(VENV_DIR)/bin/git-du" "$(BIN_DIR)/git-du"
	@echo "Installed globally to $(BIN_DIR): git-disk-usage, git-du (git du)"

uninstall-global:
	@rm -f "$(BIN_DIR)/git-disk-usage" "$(BIN_DIR)/git-du"
	@echo "Removed symlinks from $(BIN_DIR)"
