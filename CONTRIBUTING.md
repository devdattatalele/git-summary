# Contributing to GitHub Issue Resolution MCP Server

Thank you for your interest in contributing! This guide will help you get started with contributing to the project.

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- GitHub account
- Basic understanding of Model Context Protocol (MCP)

### Development Setup

1. **Fork the repository**
   ```bash
   # Click "Fork" on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/github-issue-mcp-server.git
   cd github-issue-mcp-server
   ```

2. **Set up development environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Set up environment variables**
   ```bash
   # Copy example environment file
   cp .env.example .env
   
   # Edit .env with your API keys
   # GITHUB_TOKEN=your_token_here
   # GOOGLE_API_KEY=your_key_here
   ```

4. **Verify setup**
   ```bash
   python setup_mcp_server.py
   python test_mcp_server.py
   ```

## 📋 Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### 2. Make Your Changes

- Follow the existing code style
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass

### 3. Test Your Changes

```bash
# Run the test suite
python test_mcp_server.py

# Test specific functionality
python -c "
import asyncio
from github_issue_mcp_server import your_function
# Your test code here
"

# Validate setup
python setup_mcp_server.py
```

### 4. Commit Your Changes

```bash
git add .
git commit -m "feat: add new functionality" 
# or
git commit -m "fix: resolve issue with..."
```

**Commit Message Convention:**
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `test:` for adding tests
- `refactor:` for code refactoring
- `chore:` for maintenance tasks

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:
- Clear description of changes
- Reference any related issues
- Include testing information

## 🧪 Testing Guidelines

### Running Tests

```bash
# Full test suite
python test_mcp_server.py

# Individual component tests
python -m pytest tests/ -v

# Test with specific Python version
python3.8 test_mcp_server.py
```

### Writing Tests

- Add tests for all new functionality
- Test both success and error cases
- Use descriptive test names
- Include integration tests for MCP tools

Example test structure:
```python
async def test_new_feature():
    """Test description of what this validates."""
    # Arrange
    setup_data = create_test_data()
    
    # Act
    result = await your_function(setup_data)
    
    # Assert
    assert result == expected_result
    assert "success" in result
```

## 📝 Code Style

### Python Standards

- **PEP 8**: Follow Python style guidelines
- **Type Hints**: Use type annotations for all functions
- **Docstrings**: Document all public functions
- **Error Handling**: Use proper exception handling

### Code Formatting

```bash
# Format code (if available)
black github_issue_mcp_server.py issue_solver/

# Check linting
flake8 github_issue_mcp_server.py issue_solver/
```

### Example Function Style

```python
async def example_function(param1: str, param2: int = 10) -> Dict[str, Any]:
    """
    Brief description of function purpose.
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter with default
    
    Returns:
        Dictionary containing result data
        
    Raises:
        ValueError: When param1 is invalid
        Exception: When operation fails
    """
    try:
        # Implementation here
        logger.info(f"Processing {param1}")
        result = {"success": True, "data": param1}
        return result
    except Exception as e:
        logger.error(f"Function failed: {e}")
        raise
```

## 📚 Documentation

### Updating Documentation

- Update docstrings for code changes
- Add examples for new features
- Update README.md if needed
- Update mkdocs documentation in `docs/`

### Building Documentation

```bash
# Install mkdocs
pip install mkdocs mkdocs-material

# Serve documentation locally
mkdocs serve

# Build documentation
mkdocs build
```

### Documentation Structure

```
docs/
├── index.md                    # Main documentation
├── getting_started/
│   ├── installation.md         # Installation guide
│   └── configuration.md        # Configuration guide
├── usage/
│   └── [feature].md            # Usage examples
├── api_reference/
│   └── [module].md             # API documentation
└── concepts/
    └── [concept].md            # Architecture/concepts
```

## 🐛 Bug Reports

### Before Reporting

1. Check existing issues
2. Verify with latest version
3. Test with minimal example
4. Check documentation

### Bug Report Template

```markdown
**Describe the bug**
Clear description of the issue

**To Reproduce**
Steps to reproduce:
1. Set up environment with...
2. Run command...
3. See error...

**Expected behavior**
What you expected to happen

**Environment:**
- OS: [e.g., macOS 12.0]
- Python version: [e.g., 3.9.0]
- MCP version: [e.g., 0.1.0]

**Additional context**
Logs, screenshots, etc.
```

## 💡 Feature Requests

### Feature Request Template

```markdown
**Feature Description**
Clear description of the proposed feature

**Use Case**
Why is this feature needed?

**Proposed Solution**
How should this feature work?

**Alternatives Considered**
Other approaches you've considered

**Additional Context**
Any other relevant information
```

## 🔍 Code Review Process

### For Contributors

- Keep PRs focused and small
- Write clear commit messages
- Respond to feedback promptly
- Test thoroughly before submitting

### Review Criteria

- **Functionality**: Does it work as intended?
- **Tests**: Are there adequate tests?
- **Documentation**: Is it properly documented?
- **Style**: Does it follow project conventions?
- **Performance**: Is it efficient?
- **Security**: Are there any security concerns?

## 🎯 Areas for Contribution

### High Priority

- **Performance optimization** for large repositories
- **Error handling improvements** 
- **Additional AI model support**
- **Enhanced patch generation algorithms**

### Medium Priority

- **UI improvements** for Claude Desktop
- **Additional MCP client examples**
- **Integration with other IDEs**
- **Performance monitoring tools**

### Low Priority

- **Documentation improvements**
- **Code refactoring**
- **Additional test cases**
- **Example use cases**

## 🏆 Recognition

Contributors will be:
- Listed in README.md
- Acknowledged in release notes
- Invited to project discussions
- Given credit in documentation

## 📞 Getting Help

- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Documentation**: Check docs/ directory first
- **Code Comments**: Look for inline documentation

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to GitHub Issue Resolution MCP Server! 🚀
