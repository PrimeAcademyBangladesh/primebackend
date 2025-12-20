#!/bin/bash

echo "🔧 Auto-fixing code formatting issues..."

# Fix with black
echo "Running black..."
black .

# Fix with isort
echo "Running isort..."
isort .

# Fix f-strings without placeholders
echo "Fixing unnecessary f-strings..."
find . -name "*.py" -not -path "*/venv/*" -not -path "*/.venv/*" -exec sed -i '' 's/f"\([^{}"]*\)"/"\1"/g' {} +

# Remove trailing whitespace
echo "Removing trailing whitespace..."
find . -name "*.py" -not -path "*/venv/*" -not -path "*/.venv/*" -exec sed -i '' 's/[[:space:]]*$//' {} +

echo "✅ Auto-fixes complete!"
echo "Run 'flake8 .' to check remaining issues"