# Project Guidelines & Verification

## Quality Checks Before Commit

Run the relevant verification steps before committing changes:

### 1. Python Syntax & Compilation
Always verify modified Python files:
```bash
python3 -m py_compile src/git_disk_usage/main.py
```

### 2. Linting & Formatting
When `ruff` is available:
```bash
ruff check src
```

### 3. Tests
Run the test suite:
```bash
pytest
```

## Running & Testing TUI

### Quick Run
```bash
./run.sh
# Or via Make:
make start
```

### Global CLI Test
```bash
./install.sh
git-disk-usage
```
