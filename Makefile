export UV_CACHE_DIR := $(CURDIR)/.cache/uv
export TMPDIR := $(CURDIR)/.tmp

.PHONY: seed typecheck test
seed:
	@mkdir -p .tmp
	uv run --frozen python sources/seed.py

typecheck:
	@mkdir -p .tmp
	uv run --frozen mypy

test:
	@mkdir -p .tmp
	uv run --frozen pytest
