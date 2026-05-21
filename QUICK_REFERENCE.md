# Quick Reference Card

## What You Have Now
✅ Health check endpoints ready  
✅ Multiple keep-alive strategies  
✅ Full documentation

---

## 3-Step Deployment

```bash
# 1. Deploy
git add backend/
git commit -m "Add health checks for Render"
git push

# 2. Test (wait for Render to deploy ~2-3 min)
curl https://your-app.onrender.com/api/health

# 3. Set up cron at https://www.easycron.com/
# URL: https://your-app.onrender.com/api/health
# Cron: */10 * * * *
```

---

## Health Endpoints

```bash
# Fast (for cron)
GET /api/health

# With database check
GET /api/health/detailed

# With scheduler status
GET /api/health/scheduler

# Kubernetes probes
GET /api/health/ready
GET /api/health/live
```

---

## Expected Response

```json
{
  "status": "healthy",
  "timestamp": "2024-05-21T12:45:53.123456",
  "platform": "TradeOS"
}
```

---

## Cron Setup (Pick ONE)

### EasyCron (Easiest) ⭐
https://www.easycron.com/ → Add Cron Job → Copy URL → Every 10 min

### GitHub Actions
Push `.github/workflows/keep-alive.yml` + add `RENDER_BACKEND_URL` secret

### Cron-job.org
https://cron-job.org/ → Create cron → Copy URL → Every 10 min

---

## Verification

```bash
# Manual test
curl -v https://your-app.onrender.com/api/health

# Check scheduler
curl https://your-app.onrender.com/api/scheduler/status

# View Render logs (should see GET /api/health every 10 min)
# Render Dashboard > Select App > Logs
```

---

## Files Created

```
backend/api/routes_health.py       ← NEW: Health endpoints
backend/main.py                     ← MODIFIED: Added health router
.github/workflows/keep-alive.yml    ← TEMPLATE: Copy to repo
```

---

## Success = 
App stays online + Scheduler runs + Trading continues 24/7 ✨
