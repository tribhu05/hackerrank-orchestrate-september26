"""
Decision Engine and Payment Plan Selector.
Applies official ranking criteria, evaluates candidate plans,
finds spending changes, and generates decision explanations.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
try:
    from .config import ALLOWED_AFFORDABILITY_STATUS, ALLOWED_PAYMENT_METHODS
    from .simulator import CashFlowSimulator
except ImportError:
    from code.config import ALLOWED_AFFORDABILITY_STATUS, ALLOWED_PAYMENT_METHODS
    from code.simulator import CashFlowSimulator


class DecisionEngine:
    def __init__(self, data_loader):
        self.data_loader = data_loader

    def evaluate_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a financial request and generate the complete required output row.
        """
        req_id = request["request_id"]
        u_id = request["user_id"]
        req_date = request["request_date"]
        req_amt = request["requested_amount"]
        desired_dt = request["desired_completion_date"]
        allows_partial = request["allows_partial_payment"]

        profile = self.data_loader.profiles.get(u_id)
        events = self.data_loader.events_by_user.get(u_id, [])
        options = self.data_loader.options_by_request.get(req_id, [])
        facts = self.data_loader.message_extractor.extract_user_facts(u_id, req_id)

        simulator = CashFlowSimulator(profile, events, facts)

        # 1. Calculate amount_safe_to_pay (without optional spending changes)
        safe_to_pay = simulator.calculate_amount_safe_to_pay(req_date, req_amt)

        # 2. Calculate earliest_date_for_full_payment (without optional spending changes)
        earliest_full_dt = simulator.calculate_earliest_date_for_full_payment(req_date, req_amt)

        # 3. Assemble candidate plans
        candidate_plans = []

        # (a) Full payment today
        if "full_payment" in profile["payment_methods_user_will_consider"]:
            candidate_plans.append({
                "method": "full_payment",
                "payment_option_id": "",
                "payments": [(req_date, req_amt)],
                "total_paid": req_amt,
                "first_date": req_date,
                "last_date": req_date,
                "num_payments": 1,
            })

        # (b) Supplied payment options from request_payment_options.csv
        for opt in options:
            opt_method = opt["payment_method"]
            opt_id = opt["payment_option_id"]
            num_p = opt["number_of_payments"]
            p_amt = opt["payment_amount"]
            p_freq = opt["payment_frequency_days"]
            first_p_dt = opt["first_payment_date"]
            total_payable = opt["total_payable_amount"]

            # Filter by user considered methods
            if opt_method not in profile["payment_methods_user_will_consider"]:
                continue

            # Filter installments by max_installment_months
            if opt_method == "installments":
                max_m = profile.get("max_installment_months")
                if max_m is None or num_p > max_m:
                    continue

            # Build payment schedule
            cur_dt = pd.to_datetime(first_p_dt)
            schedule = []
            for _ in range(num_p):
                schedule.append((cur_dt.strftime('%Y-%m-%d'), p_amt))
                cur_dt += timedelta(days=p_freq if p_freq > 0 else 30)

            last_p_dt = schedule[-1][0]
            candidate_plans.append({
                "method": opt_method,
                "payment_option_id": opt_id,
                "payments": schedule,
                "total_paid": total_payable,
                "first_date": first_p_dt,
                "last_date": last_p_dt,
                "num_payments": num_p,
            })

        # (c) Partial payment
        if (
            allows_partial
            and "partial_payment" in profile["payment_methods_user_will_consider"]
            and 0 < safe_to_pay < req_amt
            and earliest_full_dt is not None
            and earliest_full_dt <= desired_dt
        ):
            part2_amt = round(req_amt - safe_to_pay, 2)
            candidate_plans.append({
                "method": "partial_payment",
                "payment_option_id": "",
                "payments": [(req_date, safe_to_pay), (earliest_full_dt, part2_amt)],
                "total_paid": req_amt,
                "first_date": req_date,
                "last_date": earliest_full_dt,
                "num_payments": 2,
            })

        # (d) Wait
        if (
            "full_payment" in profile["payment_methods_user_will_consider"]
            and earliest_full_dt is not None
            and earliest_full_dt <= desired_dt
            and earliest_full_dt > req_date
        ):
            candidate_plans.append({
                "method": "wait",
                "payment_option_id": "",
                "payments": [(earliest_full_dt, req_amt)],
                "total_paid": req_amt,
                "first_date": earliest_full_dt,
                "last_date": earliest_full_dt,
                "num_payments": 1,
            })

        # 4. Evaluate candidates through simulator
        valid_plans = []
        for plan in candidate_plans:
            is_safe, min_b, _ = simulator.simulate_plan(req_date, plan["payments"])
            if is_safe:
                plan_copy = dict(plan)
                plan_copy["spending_changes"] = []
                plan_copy["min_balance"] = min_b
                valid_plans.append(plan_copy)

        # 5. If no plan is safe without spending changes, test candidate spending changes
        if not valid_plans:
            flexible_events = self._get_eligible_spending_changes(profile, events)
            if flexible_events:
                # Try changes on immediate plans (full_payment, options)
                for plan in candidate_plans:
                    changes = self._find_minimal_spending_changes(simulator, req_date, plan["payments"], flexible_events)
                    if changes:
                        plan_copy = dict(plan)
                        plan_copy["spending_changes"] = changes
                        valid_plans.append(plan_copy)
                        break

        # 6. Rank valid plans using the 6 official criteria
        best_plan = None
        if valid_plans:
            def rank_key(p):
                completes_by_deadline = 0 if p["last_date"] <= desired_dt else 1
                no_changes = 0 if len(p.get("spending_changes", [])) == 0 else 1
                total_cost = p["total_paid"]
                start_date = p["first_date"]
                fewer_payments = p["num_payments"]
                opt_id = p["payment_option_id"] if p["payment_option_id"] else "zzzzzz"
                return (completes_by_deadline, no_changes, total_cost, start_date, fewer_payments, opt_id)

            valid_plans.sort(key=rank_key)
            best_plan = valid_plans[0]

        # 7. Format output fields
        if best_plan is not None:
            method = best_plan["method"]
            changes_list = best_plan.get("spending_changes", [])
            changes_str = "|".join(changes_list) if changes_list else "none"

            # Payment plan formatting
            def _fmt_plan_amt(val):
                if abs(val - round(val)) < 1e-4:
                    return str(int(round(val)))
                return f"{val:.2f}"

            p_strs = [f"{d}:{_fmt_plan_amt(amt)}" for d, amt in best_plan["payments"]]
            plan_str = "|".join(p_strs)

            # Affordability status
            if method == "full_payment" and not changes_list:
                status = "affordable_now"
                earliest_for_output = req_date
            elif method in {"installments", "partial_payment"} or (method == "full_payment" and changes_list):
                status = "affordable_with_plan"
                earliest_for_output = earliest_full_dt if earliest_full_dt else ""
            elif method == "wait":
                status = "affordable_later"
                earliest_for_output = earliest_full_dt if earliest_full_dt else ""
            else:
                status = "not_affordable"
                earliest_for_output = earliest_full_dt if earliest_full_dt else ""

            explanation = self._generate_explanation(
                profile, request, best_plan, safe_to_pay, earliest_for_output, status
            )
        else:
            method = "not_recommended"
            status = "not_affordable"
            plan_str = "none"
            earliest_for_output = ""
            changes_str = "none"
            explanation = self._generate_not_affordable_explanation(
                profile, request, safe_to_pay, desired_dt
            )

        return {
            "request_id": req_id,
            "amount_safe_to_pay": safe_to_pay,
            "affordability_status": status,
            "recommended_payment_method": method,
            "payment_plan": plan_str,
            "earliest_date_for_full_payment": earliest_for_output,
            "spending_changes_needed": changes_str,
            "decision_explanation": explanation,
        }

    def _get_eligible_spending_changes(self, profile: Dict[str, Any], events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Find flexible, non-protected recurring events user is willing to stop or reduce.
        """
        stop_cats = profile["expense_categories_user_is_willing_to_stop"]
        reduce_cats = profile["expense_categories_user_is_willing_to_reduce"]
        protected_cats = profile["expense_categories_to_protect"]

        eligible = []
        seen_descs = set()

        # Iterate reverse chronological to get latest event_id per recurring series
        for e in sorted(events, key=lambda x: str(x['settlement_date']), reverse=True):
            cat = e['category']
            desc = e['description']
            flex = e['flexibility']
            eid = e['event_id']

            if cat in protected_cats:
                continue
            if desc in seen_descs:
                continue

            can_stop = (cat in stop_cats) and (flex in {'stoppable', 'reducible_or_stoppable'})
            can_reduce = (cat in reduce_cats) and (flex in {'reducible', 'reducible_or_stoppable'}) and (e.get('minimum_allowed_amount') is not None)

            if can_stop or can_reduce:
                seen_descs.add(desc)
                eligible.append({
                    "event_id": eid,
                    "description": desc,
                    "category": cat,
                    "amount": e['amount'],
                    "can_stop": can_stop,
                    "can_reduce": can_reduce,
                    "minimum_allowed_amount": e.get('minimum_allowed_amount'),
                })

        return eligible

    def _find_minimal_spending_changes(
        self,
        simulator: CashFlowSimulator,
        request_date: str,
        payments: List[Tuple[str, float]],
        flexible_events: List[Dict[str, Any]]
    ) -> Optional[List[str]]:
        """
        Find up to 3 spending changes that make the given plan safe.
        """
        candidate_actions = []
        for fe in flexible_events:
            if fe["can_stop"]:
                candidate_actions.append([f"stop:{fe['event_id']}"])
            if fe["can_reduce"]:
                min_amt = fe["minimum_allowed_amount"]
                min_amt_str = str(int(round(min_amt))) if abs(min_amt - round(min_amt)) < 1e-4 else f"{min_amt:.2f}"
                candidate_actions.append([f"reduce_to:{fe['event_id']}:{min_amt_str}"])

        # Try 1 change
        for act in candidate_actions:
            safe, _, _ = simulator.simulate_plan(request_date, payments, spending_changes=act)
            if safe:
                return act

        # Try combinations of 2 changes
        for i in range(len(candidate_actions)):
            for j in range(i + 1, len(candidate_actions)):
                act1 = candidate_actions[i][0]
                act2 = candidate_actions[j][0]
                # Ensure they target different events
                e1 = act1.split(':')[1]
                e2 = act2.split(':')[1]
                if e1 == e2:
                    continue
                combo = [act1, act2]
                safe, _, _ = simulator.simulate_plan(request_date, payments, spending_changes=combo)
                if safe:
                    return combo

        return None

    def _generate_explanation(
        self,
        profile: Dict[str, Any],
        request: Dict[str, Any],
        plan: Dict[str, Any],
        safe_to_pay: float,
        earliest_full_dt: str,
        status: str
    ) -> str:
        curr = profile["home_currency"]
        min_b = profile["minimum_balance_to_keep"]
        min_b_str = f"{min_b:,.2f}".rstrip('0').rstrip('.')
        method = plan["method"]
        amt = request["requested_amount"]
        amt_str = f"{amt:,.2f}".rstrip('0').rstrip('.')

        if method == "full_payment":
            changes = plan.get("spending_changes", [])
            if not changes:
                return f"Pay {curr} {amt_str} today. This leaves at least {curr} {min_b_str} available over the next 90 days."
            else:
                # Describe spending change
                change_descs = []
                for chg in changes:
                    parts = chg.split(':')
                    if parts[0] == 'stop':
                        change_descs.append("stop recurring flexible subscriptions")
                    elif parts[0] == 'reduce_to':
                        change_descs.append(f"reduce flexible spending to {curr} {parts[2]}")
                desc_str = " and ".join(change_descs).capitalize()
                return f"{desc_str}, then pay {curr} {amt_str} today. This leaves at least {curr} {min_b_str} available."

        elif method == "installments":
            n = plan["num_payments"]
            p_amt = plan["payments"][0][1]
            p_amt_str = f"{p_amt:,.2f}".rstrip('0').rstrip('.')
            first_d = plan["first_date"]
            first_dt = pd.to_datetime(first_d).strftime('%d %B %Y').lstrip('0')
            return f"Use {n} installments of {curr} {p_amt_str}, starting {first_dt}. This leaves at least {curr} {min_b_str} available."

        elif method == "partial_payment":
            safe_str = f"{safe_to_pay:,.2f}".rstrip('0').rstrip('.')
            rem_amt = amt - safe_to_pay
            rem_str = f"{rem_amt:,.2f}".rstrip('0').rstrip('.')
            dt_str = pd.to_datetime(earliest_full_dt).strftime('%d %B %Y').lstrip('0')
            return f"Pay {curr} {safe_str} today and the remaining {curr} {rem_str} on {dt_str}. This completes the full request and keeps the {curr} {min_b_str} minimum protected."

        elif method == "wait":
            dt_str = pd.to_datetime(earliest_full_dt).strftime('%d %B %Y').lstrip('0')
            return f"Pay {curr} {amt_str} in full on {dt_str}. Paying earlier would take the balance below the {curr} {min_b_str} minimum."

        return f"Payment of {curr} {amt_str} is not safe while keeping the {curr} {min_b_str} minimum protected."

    def _generate_not_affordable_explanation(
        self,
        profile: Dict[str, Any],
        request: Dict[str, Any],
        safe_to_pay: float,
        desired_dt: str
    ) -> str:
        curr = profile["home_currency"]
        min_b = profile["minimum_balance_to_keep"]
        min_b_str = f"{min_b:,.2f}".rstrip('0').rstrip('.')
        amt = request["requested_amount"]
        amt_str = f"{amt:,.2f}".rstrip('0').rstrip('.')
        dt_str = pd.to_datetime(desired_dt).strftime('%d %B %Y').lstrip('0')

        if safe_to_pay > 0:
            safe_str = f"{safe_to_pay:,.2f}".rstrip('0').rstrip('.')
            return f"Do not proceed with the {curr} {amt_str} request. Although {curr} {safe_str} is available today, the full amount cannot be completed safely within 90 days."
        return f"Do not make this payment by {dt_str}. None of the available options keeps the {curr} {min_b_str} minimum protected."
