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
echo -e "${CYAN}[1/4]${NC} Running pre-flight folder checks..."

if [ ! -d "$BACKEND_DIR" ]; then
    echo -e "${RED}❌ Error: Backend directory not found at $BACKEND_DIR${NC}"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR" ]; then
    echo -e "${RED}❌ Error: Frontend directory not found at $FRONTEND_DIR${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Folders verified.${NC}"

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: python3 is not installed or not in PATH.${NC}"
    exit 1
fi

# Check for Node and NPM
if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ Error: npm is not installed or not in PATH.${NC}"
    exit 1
fi

# --- Environment Auto-Setup ---
echo -e "\n${CYAN}[2/4]${NC} Checking virtual environment and dependencies..."

# Automatically create Python virtual environment if missing
if [ ! -d "$BACKEND_DIR/venv" ]; then
    echo -e "${YELLOW}⚙️ Virtual environment (venv) not found at $BACKEND_DIR/venv.${NC}"
    echo -e "${CYAN}Creating virtual environment...${NC}"
    python3 -m venv "$BACKEND_DIR/venv"
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Error: Failed to create virtual environment.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Virtual environment created successfully.${NC}"
fi

# Activate venv and install dependencies if requirements.txt exists
if [ -f "$BACKEND_DIR/venv/bin/activate" ]; then
    source "$BACKEND_DIR/venv/bin/activate"
    echo -e "${CYAN}Verifying backend dependencies...${NC}"
    pip install -r "$BACKEND_DIR/requirements.txt"
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Error: Failed to install backend dependencies.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Backend dependencies verified.${NC}"
    deactivate
else
    echo -e "${RED}❌ Error: Could not find virtual environment activation script.${NC}"
    exit 1
fi

# Automatically install Node dependencies if node_modules is missing
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo -e "${YELLOW}⚙️ frontend/node_modules not found. Installing node dependencies...${NC}"
    cd "$FRONTEND_DIR"
    npm install
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Error: Failed to install frontend dependencies.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Frontend dependencies installed successfully.${NC}"
    cd "$BASE_DIR"
else
    echo -e "${GREEN}✓ Frontend dependencies verified.${NC}"
fi

# Determine how to launch based on OS (MacOS supports launching separate terminal windows)
echo -e "\n${CYAN}[3/4]${NC} Select launch mode:"
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
    osascript -e 'tell application "Terminal" to do script "cd '"$BACKEND_DIR"' && echo \"--- Starting TradeOS Backend ---\" && source venv/bin/activate && python main.py"'
    
    # Wait a second to prevent race conditions
    sleep 1.5
    
    # Launch Frontend
    osascript -e 'tell application "Terminal" to do script "cd '"$FRONTEND_DIR"' && echo \"--- Starting TradeOS Frontend ---\" && npm run dev"'

    echo -e "\n${GREEN}✓ Both windows opened successfully!${NC}"
    echo -e "  👉 Backend running on: ${BOLD}http://localhost:8000${NC}"
    echo -e "  👉 Frontend running on: ${BOLD}http://localhost:5173${NC} (or http://localhost:5174)"
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
    python main.py > backend.log 2>&1 &
    BACKEND_PID=$!
    
    # Start Frontend
    echo -e "${CYAN}→ Starting Frontend server...${NC}"
    cd "$FRONTEND_DIR"
    npm run dev > frontend.log 2>&1 &
    FRONTEND_PID=$!
    
    echo -e "\n${GREEN}✓ Both services started successfully!${NC}"
    echo -e "  👉 Backend PID: $BACKEND_PID (http://localhost:8000)"
    echo -e "  👉 Frontend PID: $FRONTEND_PID (http://localhost:5173)"
    echo -e "  ${YELLOW}Tailing logs below. Press Ctrl+C to terminate both servers.${NC}"
    echo -e "======================================================================\n"
    
    # Stream both logs side-by-side or combined
    tail -f "$BACKEND_DIR/backend.log" "$FRONTEND_DIR/frontend.log"
fi
