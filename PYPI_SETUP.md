# PyPI Setup Guide for MoSMART

## Overview

This guide covers setting up MoSMART for distribution on PyPI (Python Package Index).

## Prerequisites

### 1. PyPI Account
Create account at https://pypi.org/account/register/

### 2. Test PyPI Account (Recommended)
Create account at https://test.pypi.org/account/register/

### 3. Install Required Tools
```bash
pip install --upgrade setuptools wheel twine build
```

## Configuration

### 1. Create ~/.pypirc (API Token Authentication)

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5vcmc...  # Your PyPI API token

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5vcmd...  # Your TestPyPI API token
```

### 2. Generate API Tokens

**On PyPI.org:**
1. Log in to https://pypi.org
2. Go to Account Settings → API tokens
3. Create token: "mosmart-upload"
4. Copy full token (starts with "pypi-")
5. Save in ~/.pypirc

**On TestPyPI:**
1. Log in to https://test.pypi.org
2. Go to Account Settings → API tokens
3. Create token: "mosmart-test"
4. Copy and save in ~/.pypirc

### 3. File Permissions
```bash
chmod 600 ~/.pypirc
```

## Building the Package

### Step 1: Clean Previous Builds
```bash
cd /home/magnus/mosmart
rm -rf build/ dist/ *.egg-info/
```

### Step 2: Build Distribution
```bash
python3 -m build

# Or manually:
python3 setup.py sdist bdist_wheel
```

### Step 3: Verify Build
```bash
ls -lh dist/
# Should output:
# mosmart-0.9.4-py3-none-any.whl
# mosmart-0.9.4.tar.gz
```

### Step 4: Check Package Metadata
```bash
twine check dist/*
```

## Testing Before Release

### Test on TestPyPI First

```bash
# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Verify on: https://test.pypi.org/project/mosmart/

# Test installation from TestPyPI
python3 -m venv /tmp/test-mosmart
source /tmp/test-mosmart/bin/activate
pip install -i https://test.pypi.org/simple/ mosmart
python3 -c "import smart_monitor; print('✓ Import successful')"
```

### Test with GUI Extra
```bash
pip install -i https://test.pypi.org/simple/ mosmart[gui]
```

## Uploading to PyPI

### Production Upload
```bash
# Upload to PyPI
twine upload dist/*

# Verify on: https://pypi.org/project/mosmart/
```

### Install from PyPI
```bash
# Standard installation
pip install mosmart

# With GUI support
pip install mosmart[gui]

# With development tools
pip install mosmart[dev]

# All extras
pip install mosmart[gui,dev]
```

## Package Information Displayed on PyPI

When uploaded, PyPI displays:
- **Project Name**: mosmart
- **Version**: 0.9.4
- **Author**: Magnus Modig
- **License**: GPL v3
- **Description**: S.M.A.R.T Monitor Tool for Linux
- **Long Description**: Content from README.md
- **URLs**:
  - Homepage: https://github.com/MsModig/mosmart
  - Bug Tracker: https://github.com/MsModig/mosmart/issues
  - Documentation: https://github.com/MsModig/mosmart#readme
- **Keywords**: smart monitoring disk health s.m.a.r.t linux ssd hdd
- **Requires Python**: >= 3.7
- **Classifiers**: Listed in setup.py

## Maintenance After Release

### Updating to New Version
1. Update version in setup.py: `version="0.9.5"`
2. Update CHANGELOG.md with new changes
3. Rebuild: `python3 -m build`
4. Re-upload: `twine upload dist/*`

### Yanking Old Versions (if needed)
On PyPI.org:
1. Go to project page
2. Click "Release History"
3. Click version number
4. Click "Yank release" button

## Troubleshooting

### "Invalid distribution" Error
```bash
# Fix: Check setup.py syntax
python3 -m py_compile setup.py

# Rebuild
rm -rf build/ dist/ *.egg-info/
python3 -m build
```

### "Authentication Failed" Error
```bash
# Verify token in ~/.pypirc
cat ~/.pypirc

# Test with:
twine upload --repository testpypi --dry-run dist/*
```

### Package Not Showing on PyPI
1. Wait 15-30 minutes for indexing
2. Check: https://pypi.org/project/mosmart/
3. Clear pip cache: `pip cache purge`
4. Reinstall: `pip install --force-reinstall mosmart`

## GitHub Actions (Optional - Future)

For automated uploads on release:

```yaml
# .github/workflows/publish-to-pypi.yml
name: Upload to PyPI

on:
  release:
    types: [created]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine
    - name: Build distribution
      run: python -m build
    - name: Publish to PyPI
      uses: pypa/gh-action-pypi-publish@release/v1
      with:
        password: ${{ secrets.PYPI_API_TOKEN }}
```

## Summary

### v0.9.4 Release Process
1. ✅ Code ready for distribution
2. ✅ Version updated
3. ✅ CHANGELOG created
4. ✅ PyPI configuration prepared
5. ⏳ Ready for: `twine upload dist/*`

### Quick Release Commands
```bash
# Clean and build
rm -rf build/ dist/ *.egg-info/
python3 -m build

# Check
twine check dist/*

# Test (optional)
twine upload --repository testpypi dist/*

# Release
twine upload dist/*
```

---

**Package**: mosmart  
**Current Version**: 0.9.4  
**Status**: Ready for PyPI distribution
