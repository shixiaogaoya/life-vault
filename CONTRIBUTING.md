# Contributing to LifeVault

Thank you for your interest in contributing to LifeVault! We welcome contributions from the community.

## Code of Conduct

Please be respectful and constructive in all interactions. We aim to maintain a welcoming environment for everyone.

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue with:
- A clear description of the problem
- Steps to reproduce
- Expected vs. actual behavior
- Your environment (OS, Python version, etc.)

### Suggesting Features

We welcome feature suggestions! Please create an issue with:
- A clear description of the feature
- Use cases and benefits
- Any implementation ideas

### Submitting Pull Requests

1. **Fork the repository** and create a feature branch from `main`
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Follow the coding standards**
   - Python: PEP 8 style guide
   - TypeScript: Project ESLint rules
   - Add type hints for Python code
   - Write meaningful commit messages

3. **Add tests** for new functionality
   - Unit tests for business logic
   - Integration tests for API endpoints
   - Maintain test coverage above 80%

4. **Update documentation** if needed
   - Update README.md for user-facing changes
   - Update DESIGN.md for architectural changes
   - Add inline comments for complex logic

5. **Run tests locally**
   ```bash
   cd backend
   python -m pytest tests/ -v
   ```

6. **Commit with conventional commits**
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation changes
   - `refactor:` for code refactoring
   - `test:` for test additions
   - `chore:` for maintenance tasks

   Example:
   ```bash
   git commit -m "feat: add privacy masking for phone numbers"
   ```

7. **Push and create a Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

   In your PR description:
   - Reference related issues
   - Describe what changed and why
   - Include screenshots for UI changes
   - Note any breaking changes

### Development Setup

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

**Frontend:**
```bash
cd frontend
npm install
```

### Running the Application

**Backend:**
```bash
cd backend
python -m app.main
```

**Frontend:**
```bash
cd frontend
npm run dev
```

## Project Structure

```
life-vault/
├── backend/           # FastAPI backend
│   ├── app/          # Application code
│   └── tests/        # Test suite
├── frontend/         # Nuxt 3 frontend
├── docs/             # Documentation
├── sample_data/      # Sample datasets
└── scripts/          # Utility scripts
```

## Code Review Process

- All PRs require review before merging
- We may suggest changes or ask questions
- Once approved, a maintainer will merge your PR

## Questions?

Feel free to open an issue for any questions about contributing.

## License

By contributing to LifeVault, you agree that your contributions will be licensed under the MIT License.
