# Contributing to Document Translator

Thank you for your interest in contributing! This document provides guidelines.

## Setup

1. Clone the repository
2. Create a virtual environment: `python3 -m venv venv`
3. Activate: `source venv/bin/activate`
4. Install: `pip3 install -r requirements.txt`
5. Configure `.env` with your DeepL API key

## Development

### Branch Naming
- Feature: `feature/name`
- Bug fix: `bugfix/name`
- Improvement: `improve/name`

### Commit Messages
- Clear, descriptive messages
- Start with verb: "Add", "Fix", "Update", "Remove"
- Keep first line under 50 characters

### Testing
- Write tests for new features
- Run: `pytest tests/`
- Aim for >80% code coverage

### Code Style
- Follow PEP 8
- Use 4 spaces for indentation
- Add docstrings to functions

## Pull Request Process

1. Update your branch: `git fetch origin && git rebase origin/main`
2. Push changes: `git push origin your-branch`
3. Create PR with clear description
4. Address feedback and update as needed

## Before Submitting
- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Tests added for new features
- [ ] Documentation updated
- [ ] No breaking changes

## Issues

### Bug Reports
- Describe the problem clearly
- Include reproduction steps
- Provide expected vs actual behavior
- Mention environment (OS, Python version)

### Feature Requests
- Describe desired feature
- Explain use case
- Suggest implementation if possible

## Questions?

Check existing issues, review README, or email jdwumfour@gmail.com

## License

By contributing, you agree your contributions will be under MIT License.
