# 🚀 TradeOS: Setup & Execution Guide

This document provides a clean, step-by-step walkthrough to get your TradeOS workspace configured and running on your local machine.

---

## 🏗️ What is TradeOS?
TradeOS is a live, autonomous multi-agent quantitative evaluation platform. It spawns **5 distinct AI cognitive brains** concurrently to evaluate the exact same technical indicators and live NSE stock market quote streams, generating win-rates, trade counts, drawdowns, and actionable trade decisions in real-time.

---

## 🛠️ Prerequisites & Requirements

Before booting up the platform, ensure your local machine has the following tools installed:

### 1. Core Runtimes
*   **Python 3.10 or higher**: Powers the quantitative backend, FastAPI servers, indicators, and the multi-agent execution loop.
*   **Node.js (v18.0.0+) & NPM**: Powers the React frontend dashboard and real-time visualization layer.

### 2. Private Offline Brain (Ollama)
*   **Ollama Desktop Application**: Powers the completely private, offline model **Local-Ollama (Llama 3.2 3B)** fallback agent.
    *   **macOS Setup**: Download the client from [ollama.com/download/Ollama-darwin.zip](https://ollama.com/download/Ollama-darwin.zip), unzip, and drag it to your `Applications/` folder.
    *   **Windows Setup**: Download and run the installer from [ollama.com/download/OllamaSetup.exe](https://ollama.com/download/OllamaSetup.exe).
    *   **Model Pull**: Once Ollama is running in your menu bar, open your terminal and download the model:
        ```bash
        ollama pull llama3.2
        ```

---

## ⚙️ Secure Configuration (.env)

TradeOS requires free-tier API keys to connect to remote cognitive brains. 

1. Go to the `backend/` directory.
2. Duplicate `.env.example` and rename it to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Populate the following keys:
   ```env
   # API Keys for Cognitive Brains
   GEMINI_API_KEY=your_google_gemini_api_key
   GROQ_API_KEY=your_groq_api_key
   OPENROUTER_API_KEY=your_openrouter_api_key
   DEEPSEEK_API_KEY=your_deepseek_api_key
   
   # Optional configurations (Default: http://localhost:11434)
   OLLAMA_HOST=http://localhost:11434
   ```

---

## 🚀 How to Run the Platform

We have provided two methods to run TradeOS: the **One-Command Launcher** (automatic) and the **Manual Step-by-Step** start.

### Method A: The One-Command macOS Launcher (Recommended) ⚡
We built an interactive, automated dual-process script that configures your directories, checks virtual environments, and starts both components.

In the TradeOS project root, run:
```bash
# 1. Grant execution rights
chmod +x start.sh

# 2. Fire up the launcher
./start.sh
```

#### Choose Your Mode:
*   **Choice 1: Separate Windows (Mac Terminal)**: Spawns two fresh, live Apple Terminal windows — one dedicated to your Python FastAPI backend and one to your Vite frontend. Ideal for watching live agent evaluations scroll in real-time!
*   **Choice 2: Background Mode (Combined Logs)**: Boots both servers in the background and consolidates active telemetry, streaming combined stdout directly into your active workspace terminal. Press `Ctrl + C` at any time to gracefully terminate both servers.

---

### Method B: Manual Step-by-Step Boot

If you prefer launching the servers manually in separate terminal tabs, follow this procedure:

#### Step 1: Fire up the Backend (FastAPI + Loops)
Open a terminal tab, navigate to the `backend` folder, set up your Python virtual environment, install requirements, and start the host:
```bash
# Go to backend
cd backend

# Setup Python Virtual Environment
python3 -m venv venv
source venv/bin/activate

# Install Dependencies
pip install -r requirements.txt

# Start Backend FastAPI Server
python3 main.py
```
*   👉 Backend runs on: `http://localhost:8000`

#### Step 2: Fire up the Frontend (React Vite UI)
Open a second terminal tab, navigate to the `frontend` folder, install npm modules, and run the developer hot-reload server:
```bash
# Go to frontend
cd frontend

# Install Node Packages
npm install

# Start Developer Client
npm run dev
```
*   👉 Frontend dashboard runs on: `http://localhost:5174` (or `http://localhost:5173`)

---

## 📊 Dashboard Usage Tips

1.  **Open the UI**: Direct your browser to `http://localhost:5174`.
2.  **Heatmap Stocks**: Click on any stock cell (e.g. `RELIANCE`, `TCS`) in the heatmap or table view to open its **Candlestick Chart**.
3.  **Flexible Timeline (1Y & 5Y)**: Select the timeframe buttons inside the modal overlay. The platform now automatically invokes `.timeScale().fitContent()` to scale out and display all years of historical candle records on screen in a premium layout.
4.  **Concurrently Evaluate Any Asset**: In the **Live Multi-Agent Ticker Inspector**, input any international or local ticker (e.g., `AAPL`, `INFY`) to pull real-time VWAP, Bollinger Bands, RSI, and MACD indicators, concurrently prompting all 5 AI models for their buy/short reasoning!
