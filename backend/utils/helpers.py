import pytz
from datetime import datetime
import uuid

IST = pytz.timezone("Asia/Kolkata")

def get_ist_now():
    return datetime.now(IST)

def is_market_open():
    now = get_ist_now()
    # Market open: 9:15 AM IST, Market close: 3:30 PM IST
    # Weekdays only (Monday=0, Friday=4)
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    is_weekday = now.weekday() < 5
    is_within_hours = market_open <= now <= market_close
    
    return is_weekday and is_within_hours

def generate_cycle_id():
    now = get_ist_now()
    return f"CYC-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

def format_currency(amount):
    return f"₹{amount:,.2f}"

def parse_ist_time(t_str):
    return datetime.strptime(t_str, "%H:%M").time()

