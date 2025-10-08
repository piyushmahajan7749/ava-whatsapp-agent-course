#!/bin/bash
# ============================================================================
# .env File Validator
# Checks if your .env file has proper formatting
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Validating .env file..."
echo ""

if [ ! -f .env ]; then
    echo -e "${RED}[ERROR]${NC} .env file not found!"
    exit 1
fi

issues=0
line_num=0

while IFS= read -r line || [ -n "$line" ]; do
    ((line_num++))
    
    # Skip empty lines and comments
    if [[ -z "${line// }" ]] || [[ "$line" =~ ^[[:space:]]*# ]]; then
        continue
    fi
    
    # Check for spaces around = sign
    if [[ "$line" =~ [[:space:]]=[[:space:]] ]]; then
        echo -e "${YELLOW}[WARNING]${NC} Line $line_num: Spaces around '=' sign"
        echo "  Found: $line"
        echo "  Fix to: $(echo "$line" | sed 's/ *= */=/')"
        ((issues++))
    fi
    
    # Check if line has = sign
    if [[ ! "$line" =~ = ]]; then
        echo -e "${RED}[ERROR]${NC} Line $line_num: Missing '=' sign"
        echo "  Found: $line"
        ((issues++))
    fi
    
    # Check for invalid variable names
    if [[ "$line" =~ ^[[:space:]]*([^A-Za-z_]) ]]; then
        echo -e "${RED}[ERROR]${NC} Line $line_num: Invalid variable name (must start with letter or underscore)"
        echo "  Found: $line"
        ((issues++))
    fi
    
    # Extract variable name to check
    if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*= ]]; then
        var_name="${BASH_REMATCH[1]}"
        # This is a valid variable
        echo -e "${GREEN}[✓]${NC} Line $line_num: $var_name"
    fi
    
done < .env

echo ""
echo "=================================="
if [ $issues -eq 0 ]; then
    echo -e "${GREEN}[SUCCESS]${NC} .env file is valid!"
    echo "You can proceed with deployment."
else
    echo -e "${YELLOW}[WARNING]${NC} Found $issues potential issues"
    echo ""
    echo "Common fixes:"
    echo "1. Remove spaces around = sign:"
    echo "   BAD:  VAR = value"
    echo "   GOOD: VAR=value"
    echo ""
    echo "2. Quote values with spaces:"
    echo "   GOOD: VAR=\"value with spaces\""
    echo ""
    echo "3. Remove comments on same line as values:"
    echo "   BAD:  VAR=value # comment"
    echo "   GOOD: # comment"
    echo "         VAR=value"
fi
echo "=================================="

