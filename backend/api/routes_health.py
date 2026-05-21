from fastapi import APIRouter, HTTPException
from database.connection import SessionLocal
from database.models import Agent
from datetime import datetime
import logging

router = APIRouter(prefix="/health", tags=["Health Check"])
logger = logging.getLogger(__name__)


@router.get("")
def health_check():
    """
    Basic health check endpoint.
    Simple and fast - returns immediately.
    Used by Render, load balancers, and cron jobs.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "platform": "TradeOS"
    }


@router.get("/detailed")
def detailed_health_check():
    """
    Detailed health check including database and scheduler status.
    More comprehensive but slightly slower.
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
            "database": {
                "connected": True,
                "agents_count": agent_count
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Service unavailable: Database connection failed"
        )


@router.get("/scheduler")
def scheduler_health_check():
    """
    Check the status of the trading scheduler.
    """
    try:
        from main import trading_scheduler
        
        jobs = trading_scheduler.scheduler.get_jobs()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "TradeOS",
            "scheduler": {
                "running": trading_scheduler.scheduler.running,
                "jobs_count": len(jobs),
                "jobs": [
                    {
                        "id": job.id,
                        "name": job.name,
                        "next_run": str(job.next_run_time) if job.next_run_time else "N/A",
                        "trigger": str(job.trigger)
                    } for job in jobs
                ]
            }
        }
    except Exception as e:
        logger.error(f"Scheduler health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Service unavailable: Scheduler check failed"
        )


@router.get("/ready")
def readiness_check():
    """
    Kubernetes-style readiness probe.
    Returns 200 if app is ready to serve traffic.
    """
    try:
        db = SessionLocal()
        # Quick database check
        _ = db.query(Agent).limit(1).all()
        db.close()
        
        return {"ready": True}
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Service not ready"
        )


@router.get("/live")
def liveness_check():
    """
    Kubernetes-style liveness probe.
    Returns 200 if the app process is alive.
    """
    return {"alive": True}
