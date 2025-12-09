"""Market Calendar Utilities"""
from datetime import datetime, timedelta

class MarketCalendar:
    NSE_HOLIDAYS_2024 = [
        "2024-01-26", "2024-03-08", "2024-03-25",
        "2024-08-15", "2024-10-02", "2024-12-25"
    ]
    
    NSE_HOLIDAYS_2025 = [
        "2025-01-26", "2025-02-26", "2025-03-14",
        "2025-08-15", "2025-10-02", "2025-12-25"
    ]
    
    @staticmethod
    def is_market_open(check_date=None):
        if check_date is None:
            check_date = datetime.now()
        
        if check_date.weekday() >= 5:
            return False
        
        date_str = check_date.strftime("%Y-%m-%d")
        all_holidays = MarketCalendar.NSE_HOLIDAYS_2024 + MarketCalendar.NSE_HOLIDAYS_2025
        return date_str not in all_holidays
