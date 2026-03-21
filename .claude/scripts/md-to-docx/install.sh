#!/bin/bash
# MD to DOCX converter installer

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== MD to DOCX Converter Installation ==="
echo "Install path: $SCRIPT_DIR"
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed."
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "Python: $PYTHON_VERSION"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
cd "$SCRIPT_DIR"
python3 -m venv venv

# Activate venv and install packages
echo "Installing packages..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=== Installation complete ==="
echo ""
echo "Usage:"
echo "  source ~/.claude/scripts/md-to-docx/venv/bin/activate"
echo "  python ~/.claude/scripts/md-to-docx/convert.py --help"
echo ""
echo "Or from Claude Code:"
echo "  /md-to-docx file.md"
