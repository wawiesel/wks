#!/bin/bash
# Run tests with coverage and generate reports

set -e

echo "Running tests with coverage..."

# Run unit tests with coverage (exclude smoke tests)
python -m pytest tests/ -k "not smoke" \
    --cov=wks \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-report=xml \
    -v

echo ""
echo "✓ Coverage reports generated:"
echo "  - Terminal: shown above"
echo "  - HTML: htmlcov/index.html"
echo "  - XML: coverage.xml"
echo ""
echo "To view HTML report:"
echo "  open htmlcov/index.html"
