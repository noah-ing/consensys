#!/bin/bash
#
# Consensys Code Review - Demo Script
#
# This script demonstrates various CLI usage patterns for Consensys.
# Run individual sections or the whole script to see Consensys in action.
#
# Prerequisites:
#   - pip install consensys
#   - export ANTHROPIC_API_KEY="your-api-key"

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   Consensys Code Review Demo${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check prerequisites
if ! command -v consensys &> /dev/null; then
    echo -e "${YELLOW}Error: 'consensys' command not found.${NC}"
    echo "Please install with: pip install consensys"
    exit 1
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${YELLOW}Warning: ANTHROPIC_API_KEY not set.${NC}"
    echo "Please set your API key: export ANTHROPIC_API_KEY='your-key'"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Demo 1: Quick review of vulnerable code
echo -e "${GREEN}Demo 1: Quick review of vulnerable.py${NC}"
echo "Command: consensys review examples/vulnerable.py --quick"
echo ""
consensys review "$SCRIPT_DIR/vulnerable.py" --quick || true
echo ""
echo -e "${GREEN}---${NC}"
echo ""

# Demo 2: Review inline code snippet
echo -e "${GREEN}Demo 2: Review inline code snippet${NC}"
echo "Command: consensys review --code 'password = \"admin123\"' --quick"
echo ""
consensys review --code 'password = "admin123"' --quick || true
echo ""
echo -e "${GREEN}---${NC}"
echo ""

# Demo 3: Filter by severity
echo -e "${GREEN}Demo 3: Show only HIGH+ severity issues${NC}"
echo "Command: consensys review examples/vulnerable.py --quick --min-severity HIGH"
echo ""
consensys review "$SCRIPT_DIR/vulnerable.py" --quick --min-severity HIGH || true
echo ""
echo -e "${GREEN}---${NC}"
echo ""

# Demo 4: CI mode - fail on critical issues
echo -e "${GREEN}Demo 4: CI mode - fail on CRITICAL issues${NC}"
echo "Command: consensys review examples/vulnerable.py --quick --fail-on CRITICAL"
echo ""
if consensys review "$SCRIPT_DIR/vulnerable.py" --quick --fail-on CRITICAL; then
    echo -e "${GREEN}Review passed!${NC}"
else
    echo -e "${YELLOW}Review failed due to CRITICAL issues.${NC}"
fi
echo ""
echo -e "${GREEN}---${NC}"
echo ""

# Demo 5: Review clean code
echo -e "${GREEN}Demo 5: Review well-written code${NC}"
echo "Command: consensys review examples/clean.py --quick"
echo ""
consensys review "$SCRIPT_DIR/clean.py" --quick || true
echo ""
echo -e "${GREEN}---${NC}"
echo ""

# Demo 6: View review history
echo -e "${GREEN}Demo 6: View review history${NC}"
echo "Command: consensys history"
echo ""
consensys history || true
echo ""
echo -e "${GREEN}---${NC}"
echo ""

# Demo 7: Show available teams
echo -e "${GREEN}Demo 7: Show available teams and personas${NC}"
echo "Command: consensys teams"
echo ""
consensys teams || true
echo ""
echo -e "${GREEN}---${NC}"
echo ""

# Demo 8: View metrics
echo -e "${GREEN}Demo 8: View API usage metrics${NC}"
echo "Command: consensys metrics"
echo ""
consensys metrics || true
echo ""

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   Demo Complete!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "More examples:"
echo "  consensys review file.py              # Full debate"
echo "  consensys review file.py --stream     # Live streaming"
echo "  consensys review-batch src/           # Review directory"
echo "  consensys pr 123                      # Review GitHub PR"
echo "  consensys diff                        # Review uncommitted changes"
echo "  consensys export <session-id> -f html # Export to HTML"
echo "  consensys web                         # Start web UI"
