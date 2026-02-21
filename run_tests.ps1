
$ErrorActionPreference = "Stop"

Write-Host "--- Running Ruff (Lint) ---" -ForegroundColor Cyan
uv run ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "--- Running Mypy (Type Check) ---" -ForegroundColor Cyan
uv run mypy .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "--- Running Tests (Pytest) ---" -ForegroundColor Cyan
uv run pytest tests/
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "All checks passed successfully!" -ForegroundColor Green
