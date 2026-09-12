"""
Currency conversion utilities using fixed dated exchange rates.
"""
from decimal import Decimal, ROUND_HALF_UP
import pandas as pd
try:
    from .config import EXCHANGE_RATES_CSV
except ImportError:
    from code.config import EXCHANGE_RATES_CSV


class CurrencyConverter:
    def __init__(self, fx_csv_path=EXCHANGE_RATES_CSV):
        self.fx_rates = {}
        if fx_csv_path.exists():
            df = pd.read_csv(fx_csv_path)
            for _, r in df.iterrows():
                # Key: (rate_date, from_currency, to_currency)
                key = (str(r['rate_date']).strip(), str(r['from_currency']).strip(), str(r['to_currency']).strip())
                self.fx_rates[key] = float(r['rate'])

    def convert(self, amount: float, from_curr: str, to_curr: str, settlement_date: str) -> float:
        """
        Convert amount from from_curr to to_curr on settlement_date.
        If currencies match, return amount directly.
        """
        from_curr = from_curr.strip()
        to_curr = to_curr.strip()
        if from_curr == to_curr:
            return float(amount)

        date_str = str(settlement_date).strip()[:10]
        # Direct lookup
        key = (date_str, from_curr, to_curr)
        if key in self.fx_rates:
            rate = self.fx_rates[key]
            return float(amount * rate)

        # Inverse lookup if direct not found
        inv_key = (date_str, to_curr, from_curr)
        if inv_key in self.fx_rates:
            rate = 1.0 / self.fx_rates[inv_key]
            return float(amount * rate)

        # Fallback to closest date if exact date not found
        # (Find rate with same currency pair)
        candidates = [(d, r) for (d, fc, tc), r in self.fx_rates.items() if fc == from_curr and tc == to_curr]
        if candidates:
            # Sort by date difference
            candidates.sort(key=lambda x: abs(pd.to_datetime(x[0]) - pd.to_datetime(date_str)))
            rate = candidates[0][1]
            return float(amount * rate)

        inv_candidates = [(d, r) for (d, fc, tc), r in self.fx_rates.items() if fc == to_curr and tc == from_curr]
        if inv_candidates:
            inv_candidates.sort(key=lambda x: abs(pd.to_datetime(x[0]) - pd.to_datetime(date_str)))
            rate = 1.0 / inv_candidates[0][1]
            return float(amount * rate)

        # If no rate found, raise or return amount
        return float(amount)
