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
        "enable_loss_lockout": {"type": "boolean", "bool_value": True, "desc": "Toggle single-stock daily loss lockout"},
        "enable_short_selling": {"type": "boolean", "bool_value": False, "desc": "Allow intraday short positions"},
        "min_profit_threshold_pct": {"type": "float", "numeric_value": 0.015, "desc": "Minimum take profit percentage threshold (e.g. 0.015 for 1.5%)"},
        "enable_news_sentiment": {"type": "boolean", "bool_value": True, "desc": "Enable parsing of live RSS news sentiment inside trading loop"}
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
        
    for key, value in payload.rules.items():
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
