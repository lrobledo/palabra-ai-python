# Contributing to Palabra AI Python SDK

We love your input! We want to make contributing to this project as easy and transparent as possible.

## Development Setup

1. Fork the repo and create your branch from `main`.
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/palabra-ai-python.git
   cd palabra-ai-python
   ```

3. Install uv (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

4. Create virtual environment and install in development mode:
   ```bash
   # Create virtual environment
   uv venv

   # Activate it
   src .venv/bin/activate  # On Windows: .venv\Scripts\activate

   # Install package in development mode with all dependencies
   uv sync --dev
   # OR alternatively:
   # uv pip install -e . --all-extras
   ```

5. Verify installation:
   ```bash
   python -c "import palabra_ai; print(palabra_ai.__version__)"
   ```

## Understanding Development Mode

When you use `uv sync --dev` or `uv pip install -e .`:
- The `-e` flag means "editable" (development mode)
- Your code changes are immediately reflected without reinstalling
- The package is linked, not copied, to your virtual environment
- You can edit code and test changes instantly

## Development Workflow

1. Make your changes
2. Run tests:
   ```bash
   uv run pytest -vs
   ```
3. Check code style:
   ```bash
   uv run ruff check .
   uv run ruff format .
   ```
4. Run type checking (if applicable):
   ```bash
   uv run mypy src/palabra_ai
   ```

## Testing

### Running Tests
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=palabra_ai --cov-report=html

# Run specific test file
uv run pytest tests/test_client.py

# Run tests with output
uv run pytest -vs
```

### Writing Tests
- Write tests for any new functionality
- Place tests in the `tests/` directory
- Follow existing test patterns
- Aim for high test coverage

## Code Style

We use `ruff` for both linting and formatting:

```bash
# Check for issues
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check . --fix

# Format code
uv run ruff format .
```

### Style Guidelines
- Follow PEP 8
- Use type hints where appropriate
- Write descriptive variable names
- Add docstrings to all public functions/classes
- Keep functions focused and small

## Pre-commit Hooks (Optional)

To automatically run checks before each commit:

```bash
# Install pre-commit
uv pip install pre-commit

# Set up hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Making Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/amazing-feature
   ```

2. Make your changes and test thoroughly

3. Commit with clear messages:
   ```bash
   git add .
   git commit -m "Add amazing feature"
   ```

4. Push to your fork:
   ```bash
   git push origin feature/amazing-feature
   ```

5. Open a Pull Request

## Pull Request Process

1. Ensure all tests pass
2. Update README.md if needed
3. Update documentation for new features
4. Add tests for new functionality
5. Ensure code follows style guidelines
6. Request review from maintainers

### PR Title Format
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions/changes
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

Example: `feat: Add support for batch translation`

## Troubleshooting Development Setup

### Import errors
If you get `ModuleNotFoundError: No module named 'palabra_ai'`:
```bash
# Make sure you installed in development mode
uv pip install -e .
# or
uv sync --dev
```

### Dependencies issues
```bash
# Reinstall all dependencies
uv sync --reinstall

# Or clean install
rm -rf .venv
uv venv
src .venv/bin/activate
uv sync --dev
```

### uv not found
Install uv first:
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Project Structure

```
palabra-ai-python/
├── src/
│   └── palabra_ai/      # Main package code
│       ├── __init__.py
│       ├── client.py
│       ├── config.py
│       └── ...
├── tests/               # Test files
├── examples/            # Usage examples
├── docs/                # Documentation
└── pyproject.toml       # Project configuration
```

## Reporting Issues

When reporting issues, please include:
- Python version (`python --version`)
- palabra-ai version (`pip show palabra-ai`)
- Operating system
- Minimal code example that reproduces the issue
- Full error traceback

## Questions?

Feel free to:
- Open an issue for bugs/features
- Start a discussion for questions
- Email us at api.support@palabra.ai

Thank you for contributing! 🎉
