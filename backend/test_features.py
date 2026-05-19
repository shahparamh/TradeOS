"""
TradeOS Automated Verification Suite
Tests password hashing, JWT generation, dynamic rules setting, and RiskManager guardrails.
"""

import sys
import os
import unittest
from datetime import datetime, date

# Add workspace backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.connection import Base, SessionLocal
from database.models import User, SystemRule, Trade, Agent
from api.routes_auth import hash_password, verify_password, create_access_token
from broker.risk_manager import RiskManager

class MockSettings:
    MAX_CAPITAL_PER_TRADE = 0.20
    MAX_OPEN_POSITIONS = 5
    MAX_INTRADAY_TRADES = 3
    DAILY_DRAWDOWN_LIMIT = -0.05
    AUTO_SQUARE_OFF_TIME = "15:15"

class TestTradeOSFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Dynamically build tables in the test database
        from database.connection import engine
        Base.metadata.create_all(bind=engine)
        
        # Instantiate DB session
        cls.db = SessionLocal()
        
        # Setup Test Agent
        cls.agent = cls.db.query(Agent).first()
        if not cls.agent:
            cls.agent = Agent(
                name="Test Agent",
                provider="google",
                model_name="gemini-2.0-flash",
                cash_balance=100000.0,
                is_active=True
            )
            cls.db.add(cls.agent)
            cls.db.commit()
            
        cls.settings = MockSettings()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_1_password_hashing_and_auth(self):
        """Verifies pbkdf2 password hashing, matches, and JWT token issuance."""
        raw_pw = "SuperSecurePassword123!"
        hashed = hash_password(raw_pw)
        
        self.assertNotEqual(raw_pw, hashed)
        self.assertTrue(verify_password(raw_pw, hashed))
        self.assertFalse(verify_password("wrong_password", hashed))
        
        # Test JWT generation
        token = create_access_token(data={"sub": "admin", "role": "admin"})
        self.assertTrue(len(token) > 20)

    def test_2_dynamic_rules_persistence(self):
        """Checks if dynamic rules can be retrieved and modified inside database."""
        rule_key = "test_rule_key"
        rule = self.db.query(SystemRule).filter(SystemRule.key == rule_key).first()
        
        if rule:
            self.db.delete(rule)
            self.db.commit()
            
        rule = SystemRule(
            key=rule_key,
            value_type="boolean",
            bool_value=True,
            description="Test System Rule"
        )
        self.db.add(rule)
        self.db.commit()
        
        # Verify persistence
        fetched = self.db.query(SystemRule).filter(SystemRule.key == rule_key).first()
        self.assertIsNotNone(fetched)
        self.assertTrue(fetched.bool_value)
        
        # Update and save
        fetched.bool_value = False
        self.db.commit()
        
        updated = self.db.query(SystemRule).filter(SystemRule.key == rule_key).first()
        self.assertFalse(updated.bool_value)
        
        # Clean up
        self.db.delete(updated)
        self.db.commit()

    def test_3_risk_manager_short_selling_block(self):
        """Verifies RiskManager blocks SHORT selling by default (or when toggled False)."""
        # Ensure rules exist in DB
        short_rule = self.db.query(SystemRule).filter(SystemRule.key == "enable_short_selling").first()
        if not short_rule:
            short_rule = SystemRule(key="enable_short_selling", value_type="boolean", bool_value=False)
            self.db.add(short_rule)
            self.db.commit()
            
        # Set to False
        short_rule.bool_value = False
        self.db.commit()
        
        rm = RiskManager(self.settings)
        
        decision_long = {
            "agent_id": self.agent.id,
            "symbol": "RELIANCE",
            "decision": "BUY",
            "entry_price": 2400.0,
            "quantity": 10,
            "stop_loss": 2360.0,
            "target": 2480.0,
            "ignore_hours": True
        }
        
        agent_state = {
            "agent_name": self.agent.name,
            "initial_capital": 100000.0,
            "cash_balance": 100000.0,
            "positions_count": 0,
            "today_trades_count": 0,
            "today_pnl": 0.0,
            "open_symbols": []
        }
        
        # Check standard LONG (should be permitted)
        result_long = rm.validate_trade(decision_long, agent_state)
        self.assertTrue(result_long["approved"], f"Long check failed: {result_long.get('rejection_reason')}")
        
        # Check SHORT (should be blocked)
        decision_short = decision_long.copy()
        decision_short["decision"] = "SHORT"
        decision_short["stop_loss"] = 2440.0
        decision_short["target"] = 2320.0
        
        result_short = rm.validate_trade(decision_short, agent_state)
        self.assertFalse(result_short["approved"])
        self.assertIn("Intraday short-selling is disabled", result_short["rejection_reason"])

    def test_4_risk_manager_profit_threshold(self):
        """Verifies RiskManager blocks trades that do not meet the minimum target profit margin (e.g. 1.5%)."""
        threshold_rule = self.db.query(SystemRule).filter(SystemRule.key == "min_profit_threshold_pct").first()
        if not threshold_rule:
            threshold_rule = SystemRule(key="min_profit_threshold_pct", value_type="float", numeric_value=0.015)
            self.db.add(threshold_rule)
            self.db.commit()
            
        # Set to 1.5% (0.015)
        threshold_rule.numeric_value = 0.015
        self.db.commit()
        
        rm = RiskManager(self.settings)
        
        agent_state = {
            "agent_name": self.agent.name,
            "initial_capital": 100000.0,
            "cash_balance": 100000.0,
            "positions_count": 0,
            "today_trades_count": 0,
            "today_pnl": 0.0,
            "open_symbols": []
        }
        
        # Entry at 100. Target at 100.75 (0.75% profit, less than 1.5%) - should be blocked
        decision_low = {
            "agent_id": self.agent.id,
            "symbol": "TCS",
            "decision": "BUY",
            "entry_price": 100.0,
            "quantity": 100,
            "stop_loss": 98.5,
            "target": 100.75,
            "ignore_hours": True
        }
        result_low = rm.validate_trade(decision_low, agent_state)
        self.assertFalse(result_low["approved"])
        self.assertIn("profit margin", result_low["rejection_reason"])
        
        # Entry at 100. Target at 102.50 (2.5% profit, >= 1.5%) - should be approved
        decision_high = decision_low.copy()
        decision_high["target"] = 102.50
        result_high = rm.validate_trade(decision_high, agent_state)
        self.assertTrue(result_high["approved"], f"High target check failed: {result_high.get('rejection_reason')}")

    def test_5_risk_manager_daily_loss_lockout(self):
        """Verifies RiskManager blocks entry into a symbol if a closed loss has already occurred today."""
        lockout_rule = self.db.query(SystemRule).filter(SystemRule.key == "enable_loss_lockout").first()
        if not lockout_rule:
            lockout_rule = SystemRule(key="enable_loss_lockout", value_type="boolean", bool_value=True)
            self.db.add(lockout_rule)
            self.db.commit()
            
        lockout_rule.bool_value = True
        self.db.commit()
        
        # Create a mock closed loss trade today for INFY
        mock_trade = Trade(
            agent_id=self.agent.id,
            symbol="INFY",
            action="BUY",
            position_type="LONG",
            trade_type="INTRADAY",
            entry_price=1500.0,
            exit_price=1450.0, # Loss of -50
            quantity=10,
            stop_loss=1400.0,
            target_price=1600.0,
            pnl=-500.0,
            status="CLOSED",
            confidence=80,
            entry_time=datetime.now(),
            exit_time=datetime.now()
        )
        self.db.add(mock_trade)
        self.db.commit()
        
        rm = RiskManager(self.settings)
        
        agent_state = {
            "agent_name": self.agent.name,
            "initial_capital": 100000.0,
            "cash_balance": 100000.0,
            "positions_count": 0,
            "today_trades_count": 0,
            "today_pnl": 0.0,
            "open_symbols": []
        }
        
        # Try to buy INFY again (should fail due to loss lockout)
        decision_lock = {
            "agent_id": self.agent.id,
            "symbol": "INFY",
            "decision": "BUY",
            "entry_price": 1460.0,
            "quantity": 10,
            "stop_loss": 1430.0,
            "target": 1510.0,
            "ignore_hours": True
        }
        
        result_locked = rm.validate_trade(decision_lock, agent_state)
        self.assertFalse(result_locked["approved"])
        self.assertIn("suffered a loss in INFY today", result_locked["rejection_reason"])
        
        # Clean up mock trade
        self.db.delete(mock_trade)
        self.db.commit()

if __name__ == "__main__":
    unittest.main()
