#!/bin/bash
# Auto-install script for armenian-corpus-core (Linux/macOS)

set -e  # Exit on error

echo "================================"
echo "Armenian Corpus Core - Local Installation"
echo "================================"

# Get the directory this script is in
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Installation directory: $SCRIPT_DIR"
echo ""

# Check Python version
echo "Checking Python 3.10+..."
python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
echo "Python version: $python_version"

# Check if pip is available
echo "Checking pip..."
if ! command -v pip3 &> /dev/null; then
    echo "ERROR: pip3 not found. Please install pip3 first."
    exit 1
fi

echo ""
echo "Installing armenian-corpus-core in editable mode..."
echo "This allows you to make changes to the source code and have them"
echo "reflected immediately without reinstalling."
echo ""

cd "$SCRIPT_DIR"

if [ "$1" == "--dev" ]; then
    echo "Installing with development dependencies (pytest, black, isort, mypy)..."
    pip3 install -e ".[dev]"
else
    echo "Installing core package..."
    echo "  To install with dev tools: $0 --dev"
    pip3 install -e .
fi

echo ""
echo "================================"
echo "Installation Complete!"
echo "================================"
echo ""

# Verify installation
echo "Verifying installation..."
python3 -c 'import importlib.metadata; print("✓ Version:", importlib.metadata.version("armenian-corpus-core"))'
python3 -c "from scraping.registry import get_registry; r = get_registry(); print(f'✓ Registry: {len(r.list_tools())} tools available')"

echo ""
echo "Next steps:"
echo "Run the pipeline:"
echo "     python -m scraping.runner run              # full pipeline"
echo "     python -m scraping.runner run --group scraping    # scraping only"
echo "     python -m scraping.runner run --group extraction  # extraction only"
echo "     python -m scraping.runner list                    # list all stages"
echo ""
