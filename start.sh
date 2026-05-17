#!/bin/bash

# ==============================================================================
#  TradeOS — Unified Startup Script
#  Launches both Frontend (Vite) and Backend (FastAPI + Scheduler) automatically.
# ==============================================================================

# ANSI Color Codes for premium terminal styling
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Clear screen and show header
clear
echo -e "${CYAN}${BOLD}======================================================"
echo -e "                 🚀 TradeOS PLATFORM 🚀"
echo -e "            Autonomous AI Trading Dashboard"
echo -e "======================================================${NC}"
echo ""

# Get the absolute path of the directory where the script is located
BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
BACKEND_DIR="$BASE_DIR/backend"
FRONTEND_DIR="$BASE_DIR/frontend"

# --- Pre-flight Checks ---
echo -e "${CYAN}[1/3]${NC} Running pre-flight folder checks..."

if [ ! -d "$BACKEND_DIR" ]; then
    echo -e "${RED}❌ Error: Backend directory not found at $BACKEND_DIR${NC}"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR" ]; then
    echo -e "${RED}❌ Error: Frontend directory not found at $FRONTEND_DIR${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Folders verified.${NC}"

# Verify virtual environment
if [ ! -f "$BACKEND_DIR/venv/bin/activate" ]; then
    echo -e "${YELLOW}⚠️ Warning: Virtual environment (venv) not found in $BACKEND_DIR/venv${NC}"
    echo -e "We will attempt to run using system python3, but creating a venv is recommended."
fi

# Determine how to launch based on OS (MacOS supports launching separate terminal windows)
echo -e "\n${CYAN}[2/3]${NC} Select launch mode:"
echo -e "  ${BOLD}1)${NC} ${GREEN}Separate Windows (Recommended for Mac)${NC} — Opens Backend and Frontend in separate live Terminal windows."
echo -e "  ${BOLD}2)${NC} ${CYAN}Background Mode${NC} — Runs both in the background and streams consolidated logs here."
echo ""
read -p "Enter choice [1 or 2]: " choice

cleanup() {
    echo -e "\n${RED}Stopping TradeOS processes...${NC}"
    # Kill background jobs
    jobs -p | xargs kill 2>/dev/null
    exit 0
}

# Trap Ctrl+C to run cleanup if background mode is selected
trap cleanup SIGINT

if [ "$choice" == "1" ]; then
    # ==========================================
    # MODE 1: Launch in Separate macOS Terminals
    # ==========================================
    echo -e "\n${GREEN}🚀 Launching in separate Terminal windows...${NC}"
    
    # Launch Backend
    osascript -e 'tell application "Terminal" to do script "cd '"$BACKEND_DIR"' && echo \"--- Starting TradeOS Backend ---\" && source venv/bin/activate && python3 main.py"'
    
    # Wait a second to prevent race conditions
    sleep 1.5
    
    # Launch Frontend
    osascript -e 'tell application "Terminal" to do script "cd '"$FRONTEND_DIR"' && echo \"--- Starting TradeOS Frontend ---\" && npm run dev"'

    
    echo -e "\n${GREEN}✓ Both windows opened successfully!${NC}"
    echo -e "  👉 Backend running on: ${BOLD}http://localhost:8000${NC}"
    echo -e "  👉 Frontend running on: ${BOLD}http://localhost:5174${NC}"
    echo -e "  You can close this window now."
    exit 0

else
    # ==========================================
    # MODE 2: Run in Background & Stream Logs
    # ==========================================
    echo -e "\n${GREEN}🚀 Starting both services in the background...${NC}"
    
    # Start Backend
    echo -e "${CYAN}→ Starting Backend server...${NC}"
    cd "$BACKEND_DIR"
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    fi
    python3 main.py > backend.log 2>&1 &
    BACKEND_PID=$!
    
    # Start Frontend
    echo -e "${CYAN}→ Starting Frontend server...${NC}"
    cd "$FRONTEND_DIR"
    npm run dev > frontend.log 2>&1 &
    FRONTEND_PID=$!
    
    echo -e "\n${GREEN}✓ Both services started successfully!${NC}"
    echo -e "  👉 Backend PID: $BACKEND_PID (http://localhost:8000)"
    echo -e "  👉 Frontend PID: $FRONTEND_PID (http://localhost:5174)"
    echo -e "  ${YELLOW}Tailing logs below. Press Ctrl+C to terminate both servers.${NC}"
    echo -e "======================================================================\n"
    
    # Stream both logs side-by-side or combined
    tail -f "$BACKEND_DIR/backend.log" "$FRONTEND_DIR/frontend.log"
fi
