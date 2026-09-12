"""
Data loading and indexing module.
Loads, normalizes, and indexes all datasets for the financial decision agent.
"""
from typing import Dict, List, Any, Optional
import pandas as pd
try:
    from .config import (
        REQUESTS_CSV,
        SAMPLE_REQUESTS_CSV,
        FINANCIAL_PROFILES_CSV,
        FINANCIAL_EVENTS_CSV,
        REQUEST_PAYMENT_OPTIONS_CSV,
        IMAGES_CSV,
    )
    from .currency import CurrencyConverter
    from .image_extractor import ImageExtractor
    from .message_extractor import MessageExtractor
except ImportError:
    from code.config import (
        REQUESTS_CSV,
        SAMPLE_REQUESTS_CSV,
        FINANCIAL_PROFILES_CSV,
        FINANCIAL_EVENTS_CSV,
        REQUEST_PAYMENT_OPTIONS_CSV,
        IMAGES_CSV,
    )
    from code.currency import CurrencyConverter
    from code.image_extractor import ImageExtractor
    from code.message_extractor import MessageExtractor


class DataLoader:
    def __init__(self):
        self.currency_converter = CurrencyConverter()
        self.image_extractor = ImageExtractor()
        self.message_extractor = MessageExtractor()
        
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.events_by_user: Dict[str, List[Dict[str, Any]]] = {}
        self.options_by_request: Dict[str, List[Dict[str, Any]]] = {}
        self.requests: List[Dict[str, Any]] = []
        self.samples: List[Dict[str, Any]] = []

        self._load_profiles()
        self._load_events()
        self._load_payment_options()
        self._load_requests()

    def _load_profiles(self):
        if not FINANCIAL_PROFILES_CSV.exists():
            return
        df = pd.read_csv(FINANCIAL_PROFILES_CSV)
        for _, r in df.iterrows():
            uid = str(r['user_id']).strip()
            methods = [m.strip() for m in str(r['payment_methods_user_will_consider']).split('|') if m.strip()]
            protect = [c.strip() for c in str(r['expense_categories_to_protect']).split('|') if c.strip() and c != 'nan']
            reduce_cats = [c.strip() for c in str(r['expense_categories_user_is_willing_to_reduce']).split('|') if c.strip() and c != 'nan']
            stop_cats = [c.strip() for c in str(r['expense_categories_user_is_willing_to_stop']).split('|') if c.strip() and c != 'nan']
            priorities = [p.strip() for p in str(r['financial_priorities']).split('|') if p.strip() and p != 'nan']
            
            max_inst = None
            if pd.notna(r['max_installment_months']) and str(r['max_installment_months']).strip():
                try:
                    max_inst = float(r['max_installment_months'])
                except ValueError:
                    max_inst = None

            self.profiles[uid] = {
                "user_id": uid,
                "home_currency": str(r['home_currency']).strip(),
                "current_available_balance": float(r['current_available_balance']),
                "minimum_balance_to_keep": float(r['minimum_balance_to_keep']),
                "financial_priorities": priorities,
                "expense_categories_to_protect": set(protect),
                "expense_categories_user_is_willing_to_reduce": set(reduce_cats),
                "expense_categories_user_is_willing_to_stop": set(stop_cats),
                "payment_methods_user_will_consider": set(methods),
                "max_installment_months": max_inst,
            }

    def _load_events(self):
        if not FINANCIAL_EVENTS_CSV.exists():
            return
        events_df = pd.read_csv(FINANCIAL_EVENTS_CSV)
        
        # Load image mapping
        image_event_map = {}
        if IMAGES_CSV.exists():
            img_df = pd.read_csv(IMAGES_CSV)
            for _, r in img_df.iterrows():
                image_event_map[str(r['related_event_id']).strip()] = str(r['image_id']).strip()

        for _, r in events_df.iterrows():
            eid = str(r['event_id']).strip()
            uid = str(r['user_id']).strip()
            profile = self.profiles.get(uid, {})
            home_curr = profile.get("home_currency", str(r['currency']).strip())
            
            raw_amt = r['amount']
            if pd.isna(raw_amt) or str(raw_amt).strip() == '':
                # Extract missing amount from linked image
                img_id = image_event_map.get(eid)
                if img_id:
                    extracted_amt = self.image_extractor.extract_amount(img_id)
                    amt = extracted_amt if extracted_amt is not None else 0.0
                else:
                    amt = 0.0
            else:
                amt = float(raw_amt)

            # Currency conversion to user's home currency
            evt_curr = str(r['currency']).strip()
            settlement_dt = str(r['settlement_date']).strip() if pd.notna(r['settlement_date']) else str(r['event_date']).strip()
            amt_home = self.currency_converter.convert(amt, evt_curr, home_curr, settlement_dt)

            min_allowed = None
            if pd.notna(r['minimum_allowed_amount']) and str(r['minimum_allowed_amount']).strip():
                try:
                    raw_min = float(r['minimum_allowed_amount'])
                    min_allowed = self.currency_converter.convert(raw_min, evt_curr, home_curr, settlement_dt)
                except ValueError:
                    min_allowed = None

            evt_dict = {
                "event_id": eid,
                "user_id": uid,
                "event_type": str(r['event_type']).strip(),
                "description": str(r['description']).strip(),
                "category": str(r['category']).strip(),
                "direction": str(r['direction']).strip(),
                "amount": amt_home,
                "raw_amount": amt,
                "currency": evt_curr,
                "home_currency": home_curr,
                "event_date": str(r['event_date']).strip() if pd.notna(r['event_date']) else "",
                "settlement_date": settlement_dt,
                "status": str(r['status']).strip(),
                "linked_event_id": str(r['linked_event_id']).strip() if pd.notna(r['linked_event_id']) else None,
                "flexibility": str(r['flexibility']).strip() if pd.notna(r['flexibility']) else "fixed",
                "minimum_allowed_amount": min_allowed,
            }

            if uid not in self.events_by_user:
                self.events_by_user[uid] = []
            self.events_by_user[uid].append(evt_dict)

    def _load_payment_options(self):
        if not REQUEST_PAYMENT_OPTIONS_CSV.exists():
            return
        df = pd.read_csv(REQUEST_PAYMENT_OPTIONS_CSV)
        for _, r in df.iterrows():
            rid = str(r['request_id']).strip()
            opt_dict = {
                "payment_option_id": str(r['payment_option_id']).strip(),
                "request_id": rid,
                "payment_method": str(r['payment_method']).strip(),
                "payment_amount": float(r['payment_amount']),
                "number_of_payments": int(r['number_of_payments']),
                "first_payment_date": str(r['first_payment_date']).strip(),
                "payment_frequency_days": int(r['payment_frequency_days']) if pd.notna(r['payment_frequency_days']) else 0,
                "financing_fee": float(r['financing_fee']) if pd.notna(r['financing_fee']) else 0.0,
                "total_payable_amount": float(r['total_payable_amount']),
            }
            if rid not in self.options_by_request:
                self.options_by_request[rid] = []
            self.options_by_request[rid].append(opt_dict)

    def _load_requests(self):
        if REQUESTS_CSV.exists():
            df = pd.read_csv(REQUESTS_CSV)
            for _, r in df.iterrows():
                self.requests.append(self._parse_request_row(r))

        if SAMPLE_REQUESTS_CSV.exists():
            df_samp = pd.read_csv(SAMPLE_REQUESTS_CSV)
            for _, r in df_samp.iterrows():
                self.samples.append(self._parse_request_row(r, is_sample=True))

    def _parse_request_row(self, r: pd.Series, is_sample: bool = False) -> Dict[str, Any]:
        allows_part = str(r['allows_partial_payment']).strip().lower() in {'true', '1', 'yes'}
        d = {
            "request_id": str(r['request_id']).strip(),
            "user_id": str(r['user_id']).strip(),
            "request_date": str(r['request_date']).strip(),
            "request_type": str(r['request_type']).strip(),
            "requested_amount": float(r['requested_amount']),
            "desired_completion_date": str(r['desired_completion_date']).strip(),
            "allows_partial_payment": allows_part,
            "request_text": str(r['request_text']).strip(),
        }
        if is_sample:
            d["amount_safe_to_pay"] = float(r['amount_safe_to_pay'])
            d["affordability_status"] = str(r['affordability_status']).strip()
            d["recommended_payment_method"] = str(r['recommended_payment_method']).strip()
            d["payment_plan"] = str(r['payment_plan']).strip()
            d["earliest_date_for_full_payment"] = str(r['earliest_date_for_full_payment']).strip() if pd.notna(r['earliest_date_for_full_payment']) else ""
            d["spending_changes_needed"] = str(r['spending_changes_needed']).strip()
            d["decision_explanation"] = str(r['decision_explanation']).strip()
        return d
