"""
Deterministic 90-Day Cash-Flow Simulator.
High-performance vectorized implementation modeling daily income, expenses,
pending obligations, and purchase payment plans.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd
try:
    from .config import FORECAST_DAYS
except ImportError:
    from code.config import FORECAST_DAYS

class CashFlowSimulator:
    def __init__(self, profile: Dict[str, Any], events: List[Dict[str, Any]], facts: Dict[str, Any]):
        self.profile = profile
        self.user_id = profile["user_id"]
        self.home_currency = profile["home_currency"]
        self.current_balance = float(profile["current_available_balance"])
        self.minimum_balance = float(profile["minimum_balance_to_keep"])
        self.events = events
        self.facts = facts

        # Pre-process recurring and scheduled streams
        self.historical_recurring = self._detect_recurring_events()
        self.scheduled_future_events = self._extract_future_events()

    def _detect_recurring_events(self) -> List[Dict[str, Any]]:
        recurring = []
        if not self.events:
            return recurring

        # Filter settled debits and salary
        settled_debits = [e for e in self.events if e['status'] == 'settled' and e['direction'] == 'debit' and e['settlement_date']]
        settled_salary = [e for e in self.events if e['status'] == 'settled' and e['category'] == 'salary' and e['settlement_date']]

        # 1. Salary stream
        if settled_salary:
            settled_salary.sort(key=lambda x: x['settlement_date'])
            last_sal = settled_salary[-1]
            desc_lower = last_sal.get('description', '').lower()
            
            # Check if salary ended (e.g. 'final employer payroll')
            is_ended = self.facts.get("salary_ended", False) or ('final' in desc_lower and 'payroll' in desc_lower)

            if not is_ended:
                sal_amt = float(last_sal['amount'])
                last_dt = datetime.strptime(last_sal['settlement_date'][:10], '%Y-%m-%d')
                sal_day = last_dt.day

                if self.facts.get("salary_override"):
                    sal_amt = float(self.facts["salary_override"]["amount"])
                if self.facts.get("salary_reduced"):
                    sal_amt = float(self.facts["salary_reduced"])
                if self.facts.get("salary_date_override"):
                    sal_day = int(self.facts["salary_date_override"].split('-')[-1])

                recurring.append({
                    "type": "salary",
                    "direction": "credit",
                    "category": "salary",
                    "amount": sal_amt,
                    "day_of_month": sal_day,
                    "event_id": last_sal['event_id'],
                    "flexibility": "fixed",
                    "minimum_allowed_amount": None,
                    "description": last_sal['description'],
                })

        # 2. Variable categories (groceries, transport, dining) grouped by category
        variable_cats = {'groceries', 'transport', 'dining'}
        fixed_cats = {
            'rent', 'housing', 'utilities', 'debt_repayment', 'insurance', 'education', 'family_support',
            'music_subscription', 'streaming', 'cloud_storage', 'delivery_membership', 'gym'
        }

        for cat in variable_cats:
            g = [d for d in settled_debits if d['category'] == cat]
            if not g:
                continue
            g.sort(key=lambda x: x['settlement_date'])
            dts = [datetime.strptime(x['settlement_date'][:10], '%Y-%m-%d') for x in g]
            diffs = [(dts[i] - dts[i-1]).days for i in range(1, len(dts))]
            med_interval = int(round(np.median(diffs))) if diffs else 7
            latest = g[-1]
            last_dt = dts[-1]

            recent_amts = [float(x['amount']) for x in g[-4:]]
            amt = float(np.mean(recent_amts)) if recent_amts else float(latest['amount'])

            recurring.append({
                "type": "periodic_expense",
                "direction": "debit",
                "category": cat,
                "amount": amt,
                "interval_days": med_interval,
                "last_date": last_dt,
                "event_id": latest['event_id'],
                "flexibility": latest['flexibility'],
                "minimum_allowed_amount": latest.get('minimum_allowed_amount'),
                "description": latest['description'],
            })

        # 3. Fixed commitments and Subscriptions grouped by description
        fixed_events = [d for d in settled_debits if d['category'] in fixed_cats or 'subscription' in d.get('event_type', '').lower()]
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for d in fixed_events:
            desc = d['description']
            if desc not in groups:
                groups[desc] = []
            groups[desc].append(d)

        for desc, g in groups.items():
            g.sort(key=lambda x: x['settlement_date'])
            cat = g[0]['category']
            flex = g[-1]['flexibility']
            min_allowed = g[-1]['minimum_allowed_amount']
            latest_event_id = g[-1]['event_id']
            last_dt = datetime.strptime(g[-1]['settlement_date'][:10], '%Y-%m-%d')
            amt = float(g[-1]['amount'])

            if cat == 'rent' and self.facts.get("rent_increase_pct"):
                amt *= (1.0 + float(self.facts["rent_increase_pct"]))

            if cat == 'utilities':
                recent_amts = [float(x['amount']) for x in g[-3:]]
                amt = max(recent_amts)

            recurring.append({
                "type": "monthly_expense",
                "direction": "debit",
                "category": cat,
                "amount": amt,
                "day_of_month": last_dt.day,
                "event_id": latest_event_id,
                "flexibility": flex,
                "minimum_allowed_amount": min_allowed,
                "description": desc,
            })

        # 4. Discretionary categories (shopping, entertainment, healthcare, etc.)
        # Only assume recurrence if regular cadence with >= 3 occurrences
        disc_events = [d for d in settled_debits if d['category'] not in variable_cats and d['category'] not in fixed_cats and 'subscription' not in d.get('event_type', '').lower()]
        disc_groups: Dict[str, List[Dict[str, Any]]] = {}
        for d in disc_events:
            desc = d['description']
            if desc not in disc_groups:
                disc_groups[desc] = []
            disc_groups[desc].append(d)

        for desc, g in disc_groups.items():
            if len(g) >= 3:
                g.sort(key=lambda x: x['settlement_date'])
                dts = [datetime.strptime(x['settlement_date'][:10], '%Y-%m-%d') for x in g]
                diffs = [(dts[i] - dts[i-1]).days for i in range(1, len(dts))]
                med_diff = np.median(diffs)
                if 25 <= med_diff <= 35:
                    cat = g[0]['category']
                    flex = g[-1]['flexibility']
                    min_allowed = g[-1]['minimum_allowed_amount']
                    latest_event_id = g[-1]['event_id']
                    last_dt = dts[-1]
                    amt = float(g[-1]['amount'])
                    recurring.append({
                        "type": "monthly_expense",
                        "direction": "debit",
                        "category": cat,
                        "amount": amt,
                        "day_of_month": last_dt.day,
                        "event_id": latest_event_id,
                        "flexibility": flex,
                        "minimum_allowed_amount": min_allowed,
                        "description": desc,
                    })

        return recurring

    def _extract_future_events(self) -> List[Dict[str, Any]]:
        future = []
        for e in self.events:
            status = e['status']
            direction = e['direction']
            eid = e['event_id']

            if eid in self.facts.get("internal_transfers", set()):
                continue
            if eid in self.facts.get("unrealized_investments", set()) or status == 'unrealized':
                continue
            if status in {'cancelled', 'failed'}:
                continue
            if direction == 'credit' and status == 'pending':
                continue
            if eid in self.facts.get("pending_credits_to_ignore", set()):
                continue

            if status in {'pending', 'scheduled'}:
                future.append(e)

        for inv in self.facts.get("confirmed_invoices", []):
            future.append({
                "event_id": f"msg_inv_{inv['settlement_date']}",
                "direction": "credit",
                "amount": float(inv["amount"]),
                "settlement_date": inv["settlement_date"],
            })

        if self.facts.get("salary_first"):
            first_sal = self.facts["salary_first"]
            future.append({
                "event_id": f"msg_first_sal_{first_sal['credit_date']}",
                "direction": "credit",
                "amount": float(first_sal["amount"]),
                "settlement_date": first_sal["credit_date"],
            })

        return future

    def _build_base_cashflow(self, start_date_str: str, days: int = FORECAST_DAYS):
        """
        Pre-compute base daily credits and debits arrays for ultra-fast vectorized simulation.
        """
        start_dt = datetime.strptime(start_date_str[:10], '%Y-%m-%d')
        date_list = [start_dt + timedelta(days=i) for i in range(days + 1)]
        
        base_credits = np.zeros(days + 1, dtype=np.float64)
        base_debits = np.zeros(days + 1, dtype=np.float64)
        
        # Event ID to debit day indices mapping for fast spending changes
        event_debit_map: Dict[str, List[Tuple[int, float]]] = {}

        # 1. Scheduled future events
        for fe in self.scheduled_future_events:
            set_dt = datetime.strptime(fe['settlement_date'][:10], '%Y-%m-%d')
            day_idx = (set_dt - start_dt).days
            if day_idx < 0:
                day_idx = 0
            if 0 <= day_idx <= days:
                amt = float(fe['amount'])
                eid = fe.get('event_id', '')
                if fe['direction'] == 'credit':
                    base_credits[day_idx] += amt
                elif fe['direction'] == 'debit':
                    base_debits[day_idx] += amt
                    if eid:
                        if eid not in event_debit_map:
                            event_debit_map[eid] = []
                        event_debit_map[eid].append((day_idx, amt))

        # 2. Recurring streams
        for rec in self.historical_recurring:
            eid = rec['event_id']
            amt = float(rec['amount'])

            if rec['type'] == 'salary':
                if self.facts.get("salary_ended"):
                    continue
                sal_day = rec['day_of_month']
                for idx, cur_dt in enumerate(date_list):
                    days_in_m = 31 if cur_dt.month in {1, 3, 5, 7, 8, 10, 12} else (28 if cur_dt.month == 2 else 30)
                    if cur_dt.day == min(sal_day, days_in_m):
                        cur_amt = amt
                        if self.facts.get("arrears_adjustment") and idx < 31:
                            cur_amt += float(self.facts["arrears_adjustment"])
                        base_credits[idx] += cur_amt

            elif rec['type'] == 'monthly_expense':
                target_day = rec['day_of_month']
                for idx, cur_dt in enumerate(date_list):
                    # Check target day (clamp to days in month)
                    days_in_m = 31 if cur_dt.month in {1, 3, 5, 7, 8, 10, 12} else (28 if cur_dt.month == 2 else 30)
                    if cur_dt.day == min(target_day, days_in_m):
                        base_debits[idx] += amt
                        if eid not in event_debit_map:
                            event_debit_map[eid] = []
                        event_debit_map[eid].append((idx, amt))

            elif rec['type'] == 'periodic_expense':
                interval = rec['interval_days']
                last_dt = rec.get('last_date', start_dt)
                next_dt = last_dt + timedelta(days=interval)
                while next_dt < start_dt:
                    next_dt += timedelta(days=interval)

                while next_dt <= date_list[-1]:
                    idx = (next_dt - start_dt).days
                    if 0 <= idx <= days:
                        base_debits[idx] += amt
                        if eid not in event_debit_map:
                            event_debit_map[eid] = []
                        event_debit_map[eid].append((idx, amt))
                    next_dt += timedelta(days=interval)

        return start_dt, base_credits, base_debits, event_debit_map

    def simulate_plan(
        self,
        start_date_str: str,
        payments: List[Tuple[str, float]],
        spending_changes: Optional[List[str]] = None,
        days: int = FORECAST_DAYS,
        cached_base=None
    ) -> Tuple[bool, float, np.ndarray]:
        """
        Ultra-fast vectorized simulation using pre-computed NumPy cash-flow arrays.
        """
        if cached_base is None:
            start_dt, base_credits, base_debits, event_debit_map = self._build_base_cashflow(start_date_str, days)
        else:
            start_dt, base_credits, base_debits, event_debit_map = cached_base

        cur_debits = base_debits.copy()

        # Apply spending changes
        if spending_changes:
            for chg in spending_changes:
                parts = chg.split(':')
                action = parts[0]
                eid = parts[1]
                if eid in event_debit_map:
                    for day_idx, orig_amt in event_debit_map[eid]:
                        if action == 'stop':
                            cur_debits[day_idx] -= orig_amt
                        elif action == 'reduce_to' and len(parts) >= 3:
                            new_amt = float(parts[2])
                            reduction = max(0.0, orig_amt - new_amt)
                            cur_debits[day_idx] -= reduction

        # Apply planned purchase payments
        purchase_deductions = np.zeros(days + 1, dtype=np.float64)
        for p_date_str, p_amt in payments:
            p_dt = datetime.strptime(p_date_str[:10], '%Y-%m-%d')
            day_idx = (p_dt - start_dt).days
            if 0 <= day_idx <= days:
                purchase_deductions[day_idx] += float(p_amt)

        # Vectorized balance trajectory
        daily_net = base_credits - cur_debits - purchase_deductions
        balance_curve = self.current_balance + np.cumsum(daily_net)
        min_balance = float(np.min(balance_curve))

        is_safe = min_balance >= self.minimum_balance - 1e-4
        return is_safe, min_balance, balance_curve

    def calculate_amount_safe_to_pay(self, request_date: str, requested_amount: float) -> float:
        """
        Vectorized binary search for amount_safe_to_pay on request_date.
        """
        base = self._build_base_cashflow(request_date, FORECAST_DAYS)
        
        # Test full payment
        safe, _, _ = self.simulate_plan(request_date, [(request_date, requested_amount)], cached_base=base)
        if safe:
            return float(requested_amount)

        # Test zero payment
        safe_zero, min_b, _ = self.simulate_plan(request_date, [], cached_base=base)
        if not safe_zero:
            return 0.0

        max_safe = max(0.0, min(requested_amount, min_b - self.minimum_balance))
        low = 0.0
        high = max_safe
        best = 0.0

        for _ in range(25):
            mid = (low + high) / 2.0
            is_safe, _, _ = self.simulate_plan(request_date, [(request_date, mid)], cached_base=base)
            if is_safe:
                best = mid
                low = mid
            else:
                high = mid

        best = float(np.floor(best * 100.0) / 100.0)
        while best > 0.0:
            is_safe, _, _ = self.simulate_plan(request_date, [(request_date, best)], cached_base=base)
            if is_safe:
                break
            best -= 0.01

        return max(0.0, best)

    def calculate_earliest_date_for_full_payment(
        self,
        request_date: str,
        requested_amount: float,
        days: int = FORECAST_DAYS
    ) -> Optional[str]:
        """
        Find earliest date where full payment is safe without spending changes.
        """
        base = self._build_base_cashflow(request_date, days)
        start_dt = base[0]

        # Test request_date
        safe_today, _, _ = self.simulate_plan(request_date, [(request_date, requested_amount)], cached_base=base)
        if safe_today:
            return request_date

        # Check candidate dates
        for offset in range(1, days + 1):
            cand_dt = start_dt + timedelta(days=offset)
            cand_str = cand_dt.strftime('%Y-%m-%d')
            is_safe, _, _ = self.simulate_plan(request_date, [(cand_str, requested_amount)], cached_base=base)
            if is_safe:
                return cand_str

        return None
