.PHONY: format lint typecheck architecture-check governance-check test test-fast test-contract test-pkg integration ci-fast

PKG ?=

format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run pyright

architecture-check:
	uv run pytest -m architecture

governance-check:
	node .claude/check-docs.mjs

test:
	uv run pytest -m "not live_external"

test-fast: governance-check
	uv run pytest -m "architecture or unit"

test-contract: governance-check
	uv run pytest -m "architecture or contract"

test-pkg:
	@test -n "$(PKG)" || { echo "PKG=libs/<feature> or apps/<app> is required"; exit 1; }
	uv run pytest "src/$(PKG)"

integration:
	uv run pytest -m live_external

ci-fast: lint typecheck architecture-check governance-check test
