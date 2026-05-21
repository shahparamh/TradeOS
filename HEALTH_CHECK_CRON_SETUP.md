# Health Check & Cron Job Setup for Render Deployment

## Problem
Render's free tier puts applications to sleep after 15 minutes of inactivity. This causes the TradeOS backend to become unresponsive and the trading scheduler to stop.

## Solution
Set up a health check endpoint and configure a cron job service to ping it periodically.

---

## 1. Backend Health Route ✅ (Already Implemented)

The FastAPI backend already has health endpoints:

- **`GET /api/health`** - Returns `{"status": "alive", "platform": "TradeOS"}`
- **`GET /`** - Returns `{"status": "TradeOS Backend is running"}`

### Enhanced Health Check (Optional)
You can add a more detailed health endpoint in `backend/api/routes_health.py`:

```python
from fastapi import Router, HTTPException
from database.connection import SessionLocal
from database.models import Agent
from datetime import datetime

router = Router()

@router.get("/health")
def health_check():
    """
    Comprehensive health check endpoint.
    Returns the status of the backend and key dependencies.
    """
    try:
        db = SessionLocal()
        
        # Check database connectivity
        agent_count = db.query(Agent).count()
        db.close()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "TradeOS",
            "database": "connected",
            "agent_count": agent_count
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

@router.get("/health/detailed")
def detailed_health_check():
    """
    Detailed health check including scheduler status.
    """
    from main import trading_scheduler
    
    try:
        db = SessionLocal()
        agent_count = db.query(Agent).count()
        db.close()
        
        jobs = trading_scheduler.scheduler.get_jobs()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "TradeOS",
            "database": "connected",
            "agent_count": agent_count,
            "scheduler": {
                "running": trading_scheduler.scheduler.running,
                "jobs_count": len(jobs)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")
```

Add to `backend/main.py` routers section:
```python
from api.routes_health import router as health_router
app.include_router(health_router, prefix="/api")
```

---

## 2. Cron Job Setup Options

### **Option A: Using EasyCron (Recommended for Simplicity)**

1. Go to **https://www.easycron.com/**
2. Sign up for a free account
3. Create a new cron job with these settings:
   - **URL**: `https://your-render-app.onrender.com/api/health`
   - **Cron Expression**: `*/10 * * * *` (every 10 minutes)
   - **HTTP Method**: GET
   - **Description**: TradeOS Backend Keep-Alive

4. Save and enable the cron job
5. View logs to confirm it's running

### **Option B: Using Cron-job.org (Free Alternative)**

1. Go to **https://cron-job.org/**
2. Create a new cron job:
   - **URL**: `https://your-render-app.onrender.com/api/health`
   - **Schedule**: Set to run every 10 minutes
   - **HTTP Method**: GET

3. Activate the job

### **Option C: Using GitHub Actions (If You Have the Repo)**

Create `.github/workflows/keep-alive.yml`:

```yaml
name: Keep Render App Alive

on:
  schedule:
    # Every 10 minutes
    - cron: '*/10 * * * *'

jobs:
  keep-alive:
    runs-on: ubuntu-latest
    steps:
      - name: Ping health endpoint
        run: |
          curl -f https://your-render-app.onrender.com/api/health || exit 1
```

### **Option D: Advanced - Using APScheduler (In-App Scheduler)**

Since your backend already uses APScheduler, you can add a self-pinging mechanism:

Add to `backend/scheduler/trading_loop.py`:

```python
def schedule_keep_alive(self):
    """
    Schedule a job to prevent Render from sleeping.
    This pings an internal endpoint to keep the app warm.
    """
    import requests
    from config import settings
    
    def keep_alive_ping():
        try:
            # Ping own health endpoint
            url = f"{settings.BACKEND_URL}/api/health"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print(f"[Keep-Alive] Pinged health endpoint: {response.json()}")
        except Exception as e:
            print(f"[Keep-Alive] Error pinging health endpoint: {str(e)}")
    
    # Schedule every 10 minutes (600 seconds)
    self.scheduler.add_job(
        keep_alive_ping,
        'interval',
        seconds=600,
        id='keep_alive_job',
        name='Keep Render App Alive',
        replace_existing=True,
        max_instances=1
    )
```

Then call this in `TradingScheduler.__init__()`:
```python
self.schedule_keep_alive()
```

---

## 3. Render Configuration

To ensure your app stays running:

1. **Update `render.yaml` or Render Dashboard:**
   - Set auto-deploy to enabled
   - Increase timeout settings if needed

2. **Add to `render.yaml`:**
```yaml
services:
  - type: web
    name: tradeos-backend
    env: python
    buildCommand: pip install -r backend/requirements.txt
    startCommand: python backend/main.py
    envVars:
      - key: PORT
        value: 8000
    # Keep the app running
    maxInstances: 1
```

---

## 4. Verification Steps

1. **Check health endpoint manually:**
   ```bash
   curl https://your-render-app.onrender.com/api/health
   ```

2. **Monitor Render logs** to see requests coming in from your cron job

3. **Verify scheduler is still running:**
   ```bash
   curl https://your-render-app.onrender.com/api/scheduler/status
   ```

---

## 5. Recommended Setup

For **TradeOS**, I recommend:
- **Primary**: Use **EasyCron** (simplest, most reliable)
- **Backup**: Add **GitHub Actions** workflow as a secondary keep-alive
- **Tertiary**: Add APScheduler self-ping for extra redundancy

This multi-layer approach ensures your backend never goes to sleep.

---

## Files Modified
- `backend/main.py` - Already has health endpoints ✅
- (Optional) `backend/api/routes_health.py` - For enhanced health checking
- (Optional) `backend/scheduler/trading_loop.py` - For in-app keep-alive

## Next Steps
1. Deploy to Render
2. Set up EasyCron cron job pointing to `/api/health`
3. Monitor logs for the first 24 hours
4. Adjust cron frequency if needed
