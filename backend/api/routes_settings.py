from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import SystemRule
from api.routes_auth import get_current_user
from pydantic import BaseModel
from typing import Dict, Any

router = APIRouter(prefix="/settings", tags=["System Settings"])

class RuleUpdate(BaseModel):
    rules: Dict[str, Any]

@router.get("/rules")
def get_system_rules(db: Session = Depends(get_db)):
    rules = db.query(SystemRule).all()
    
    # Standard fallback defaults if database is not seeded yet
    default_values = {
        "enable_loss_lockout": {"type": "boolean", "bool_value": False, "desc": "Toggle single-stock daily loss lockout"},
        "enable_short_selling": {"type": "boolean", "bool_value": True, "desc": "Allow intraday short positions"},
        "min_profit_threshold_pct": {"type": "float", "numeric_value": 0.015, "desc": "Minimum take profit percentage threshold (e.g. 0.015 for 1.5%)"},
        "enable_news_sentiment": {"type": "boolean", "bool_value": True, "desc": "Enable parsing of live RSS news sentiment inside trading loop"},
        "max_open_positions": {"type": "float", "numeric_value": 40.0, "desc": "Maximum open positions per agent"},
        "max_capital_per_trade_pct": {"type": "float", "numeric_value": 0.50, "desc": "Maximum capital per trade percentage (0.50 = 50%)"},
        "max_intraday_trades": {"type": "float", "numeric_value": 70.0, "desc": "Maximum intraday trades per agent per day"},
        "daily_drawdown_limit": {"type": "float", "numeric_value": -0.05, "desc": "Daily loss drawdown limit (e.g., -0.05 for -5%)"},
        "min_confidence": {"type": "float", "numeric_value": 65.0, "desc": "Minimum model confidence floor to enter trade (0-100)"},
        "max_stop_loss_distance": {"type": "float", "numeric_value": 0.07, "desc": "Maximum allowed stop loss distance (e.g. 0.07 for 7%)"},
        "min_risk_reward_ratio": {"type": "float", "numeric_value": 2.0, "desc": "Minimum risk-reward ratio allowed"},
        "max_consecutive_losses": {"type": "float", "numeric_value": 5.0, "desc": "Circuit breaker max consecutive daily losses"},
        "max_trades_per_stock_daily": {"type": "float", "numeric_value": 5.0, "desc": "Maximum trades per stock per model per day"},
        "entry_start_hour": {"type": "float", "numeric_value": 9.25, "desc": "Allowed entry start hour (e.g., 9.25 for 9:15 AM)"},
        "entry_end_hour": {"type": "float", "numeric_value": 14.0, "desc": "Allowed entry end hour (e.g., 14.0 for 2:00 PM)"},
        "enable_fno_trading": {"type": "boolean", "bool_value": True, "desc": "Toggle Futures & Options (F&O) trading and scanning for AI models"},
        "enable_equity_trading": {"type": "boolean", "bool_value": False, "desc": "Toggle Equity trading and scanning for AI models"},
        "max_trades_daily_per_model": {"type": "float", "numeric_value": 20.0, "desc": "Maximum trades per model across all symbols per day"},
        "equity_ai_cooldown_min": {"type": "float", "numeric_value": 5.0, "desc": "AI request cooldown for Equity symbols in minutes"},
        "fno_ai_cooldown_min": {"type": "float", "numeric_value": 5.0, "desc": "AI request cooldown for F&O symbols in minutes"},
        "starting_capital_per_agent": {"type": "float", "numeric_value": 5000000.0, "desc": "Starting balance per AI agent upon platform reset"}
    }
    
    # Build actual map
    rule_map = {}
    db_keys = {r.key for r in rules}
    
    # Add rules from DB
    for rule in rules:
        val = rule.bool_value if rule.value_type == "boolean" else rule.numeric_value
        rule_map[rule.key] = {
            "value": val,
            "type": rule.value_type,
            "description": rule.description
        }
        
    # Seed missing defaults dynamically
    needs_commit = False
    for key, spec in default_values.items():
        if key not in db_keys:
            new_rule = SystemRule(
                key=key,
                value_type=spec["type"],
                bool_value=spec.get("bool_value"),
                numeric_value=spec.get("numeric_value"),
                description=spec["desc"]
            )
            db.add(new_rule)
            needs_commit = True
            val = spec.get("bool_value") if spec["type"] == "boolean" else spec.get("numeric_value")
            rule_map[key] = {
                "value": val,
                "type": spec["type"],
                "description": spec["desc"]
            }
            
    if needs_commit:
        db.commit()
        
    return rule_map

@router.put("/rules")
def update_system_rules(payload: RuleUpdate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    # Verify current user is admin or authorized
    if current_user.role not in ["admin", "trader"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update system trading rules."
        )
        
    rules_dict = dict(payload.rules)
    
    # Enforce mutual exclusivity
    if rules_dict.get("enable_equity_trading") is True:
        rules_dict["enable_fno_trading"] = False
    elif rules_dict.get("enable_fno_trading") is True:
        rules_dict["enable_equity_trading"] = False
        
    for key, value in rules_dict.items():
        rule = db.query(SystemRule).filter(SystemRule.key == key).first()
        if not rule:
            # Create dynamically if doesn't exist
            val_type = "boolean" if isinstance(value, bool) else "float"
            rule = SystemRule(key=key, value_type=val_type)
            db.add(rule)
            
        if rule.value_type == "boolean":
            # Cast / evaluate boolean value
            rule.bool_value = bool(value)
        else:
            # Cast numeric value
            rule.numeric_value = float(value)
            
    db.commit()
    return {"status": "success", "message": "System trading rules updated successfully."}

class ResetPayload(BaseModel):
    starting_capital: float

@router.post("/reset")
def reset_database(payload: ResetPayload, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    if current_user.role not in ["admin", "trader"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to reset the platform."
        )
        
    try:
        from database.models import Agent, Trade, Position, DailyPerformance, AIResponse, AgentDailyStrategy

        # Fleet mode only — resetting the fleet's capital must never touch the Survival Arena's
        # tiny paper balances or its separate trade/debate history.
        fleet_agent_ids = [a.id for a in db.query(Agent.id).filter(Agent.mode != "SURVIVAL").all()]

        db.query(Position).filter(Position.agent_id.in_(fleet_agent_ids)).delete(synchronize_session=False)
        db.query(Trade).filter(Trade.agent_id.in_(fleet_agent_ids)).delete(synchronize_session=False)
        db.query(DailyPerformance).filter(DailyPerformance.agent_id.in_(fleet_agent_ids)).delete(synchronize_session=False)
        db.query(AgentDailyStrategy).filter(AgentDailyStrategy.agent_id.in_(fleet_agent_ids)).delete(synchronize_session=False)
        db.query(AIResponse).filter(AIResponse.agent_id.in_(fleet_agent_ids)).delete(synchronize_session=False)

        agents = db.query(Agent).filter(Agent.mode != "SURVIVAL").all()
        for agent in agents:
            agent.cash_balance = payload.starting_capital
            agent.total_pnl = 0.0

        db.commit()
        return {"status": "success", "message": f"Platform reset successfully! Cash balances refreshed to ₹{payload.starting_capital:,.2f}."}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database reset failed: {str(e)}"
        )
