# Health Check & Cron Job Setup for Render Deployment

## Problem Solved ✅
Render's free tier puts apps to sleep after 15 minutes of inactivity. This breaks the trading scheduler.

## Solution Implemented
- ✅ Enhanced health check endpoints in `backend/api/routes_health.py`
- ✅ Updated `backend/main.py` to use new health routes
- ✅ Multiple cron job setup options (EasyCron, GitHub Actions, etc.)

---

## Files Created/Modified

### New Files
```
backend/api/routes_health.py  - Enhanced health check endpoints
```

### Modified Files
```
backend/main.py - Added health router import and registration
```

### Reference Files (in session)
```
.github/workflows/keep-alive.yml - GitHub Actions workflow (copy to repo)
```

---

## Available Health Endpoints

After deployment, test these:

```bash
# Basic health check (fastest, for cron jobs)
curl https://your-app.onrender.com/api/health

# Detailed health with database check
curl https://your-app.onrender.com/api/health/detailed

# Scheduler and jobs status
curl https://your-app.onrender.com/api/health/scheduler

# Kubernetes readiness probe
curl https://your-app.onrender.com/api/health/ready

# Kubernetes liveness probe
curl https://your-app.onrender.com/api/health/live
```

---

## 🚀 Deployment Steps

### 1. Deploy to Render
```bash
cd backend
git add api/routes_health.py main.py
git commit -m "Add health check endpoints for Render keep-alive

- Create enhanced health check routes with multiple endpoints
- Update main.py to register health router
- Enables cron jobs to keep app awake"
git push
```

### 2. Test Deployment
Once deployed, verify the endpoint works:
```bash
curl https://your-app.onrender.com/api/health
```

### 3. Set Up Cron Job

---

## Cron Job Setup (Choose ONE)

### Option A: EasyCron ⭐ (RECOMMENDED)
1. Go to https://www.easycron.com/
2. Sign up (free)
3. Add new cron job:
   - URL: `https://your-app.onrender.com/api/health`
   - Cron: `*/10 * * * *` (every 10 minutes)
4. Save and enable

### Option B: GitHub Actions (Free)
1. Copy `.github/workflows/keep-alive.yml` to your repo
2. Add GitHub secret: `RENDER_BACKEND_URL = https://your-app.onrender.com`
3. Push to GitHub

### Option C: Cron-job.org (Free)
1. Go to https://cron-job.org/
2. Create cron job:
   - URL: `https://your-app.onrender.com/api/health`
   - Schedule: Every 10 minutes

---

## Verification

### Check Logs in Render
1. Go to Render dashboard
2. Select your app
3. View **Logs** tab
4. Should see GET `/api/health` requests every 10 minutes

### Manual Check
```bash
# Should return 200 status and JSON
curl -v https://your-app.onrender.com/api/health

# Check scheduler is running
curl https://your-app.onrender.com/api/scheduler/status
```

---

## Success Indicators
- ✅ Cron job shows successful executions every 10 minutes
- ✅ Render logs show incoming health check requests
- ✅ Scheduler status shows `"running": true`
- ✅ App doesn't go to sleep (no "waking up" messages in logs)

---

## For Maximum Reliability
Set up **multiple keep-alive methods**:
1. EasyCron (primary)
2. GitHub Actions (backup)
3. Cron-job.org (secondary backup)

All are free and take 5-10 minutes to set up.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Health endpoint returns 503 | Check database connection in Render settings |
| Cron job shows "Failed" | Verify app URL is correct (no typos) |
| App still goes to sleep | Ensure cron is enabled and running every 10 min |
| Scheduler not running | Check Render app logs for startup errors |

---

## Next Steps
1. Deploy changes to Render
2. Test `/api/health` endpoint
3. Set up at least one cron job (EasyCron recommended)
4. Monitor Render logs for 24 hours to verify
5. (Optional) Add backup cron services for redundancy

✨ **That's it! Your backend will now stay awake.** ✨
