import datetime

def is_market_holiday(date_obj: datetime.date = None) -> bool:
    """
    Checks if a given date is a market holiday on the NSE.
    If no date is provided, checks today.
    """
    if date_obj is None:
        date_obj = datetime.date.today()
        
    # Standard NSE holidays for the current year
    # Update this list annually or integrate with an API for dynamic holidays.
    nse_holidays_2026 = [
        datetime.date(2026, 1, 26),  # Republic Day
        datetime.date(2026, 3, 2),   # Holi (approx)
        datetime.date(2026, 4, 3),   # Mahavir Jayanti (approx)
        datetime.date(2026, 4, 10),  # Good Friday
        datetime.date(2026, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti
        datetime.date(2026, 5, 1),   # Maharashtra Day
        datetime.date(2026, 8, 15),  # Independence Day
        datetime.date(2026, 9, 7),   # Ganesh Chaturthi
        datetime.date(2026, 10, 2),  # Mahatma Gandhi Jayanti
        datetime.date(2026, 10, 19), # Dussehra
        datetime.date(2026, 11, 8),  # Diwali-Laxmi Puja (approx)
        datetime.date(2026, 11, 23), # Gurunanak Jayanti
        datetime.date(2026, 12, 25), # Christmas
    ]
    
    if date_obj in nse_holidays_2026:
        return True
        
    # Weekends are checked separately in the trading loop, but we can also check here
    if date_obj.weekday() >= 5:
        return True
        
    return False
