"""
Message parsing and structured fact extraction.
Extracts financial evidence from messages while protecting against prompt injection.
"""
import re
from typing import Dict, Any, List, Optional
import pandas as pd
try:
    from .config import MESSAGES_CSV
except ImportError:
    from code.config import MESSAGES_CSV


# Prompt injection signatures
INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|prior)\s+instructions",
    r"override\s+(the\s+)?(rules|system|decision)",
    r"approve\s+(this\s+|the\s+)?purchase",
    r"system\s*:\s*",
    r"you\s+are\s+now\s+",
    r"disregard\s+",
    r"forget\s+(everything|prior)",
]

class MessageExtractor:
    def __init__(self, messages_csv_path=MESSAGES_CSV):
        self.messages_df = pd.read_csv(messages_csv_path) if messages_csv_path.exists() else pd.DataFrame()

    def is_prompt_injection(self, text: str) -> bool:
        """Detect prompt injection attempts in untrusted messages."""
        text_lower = text.lower()
        for pat in INJECTION_PATTERNS:
            if re.search(pat, text_lower):
                return True
        return False

    def extract_user_facts(self, user_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract all valid, verified financial facts from messages associated with user_id or request_id.
        """
        facts: Dict[str, Any] = {
            "salary_override": None,
            "salary_date_override": None,
            "salary_reduced": None,
            "salary_ended": False,
            "salary_first": None,
            "arrears_adjustment": None,
            "rent_increase_pct": None,
            "confirmed_invoices": [],  # list of (date, amount)
            "internal_transfers": set(),
            "pending_credits_to_ignore": set(),
            "unrealized_investments": set(),
        }

        if self.messages_df.empty:
            return facts

        user_msgs = self.messages_df[
            (self.messages_df['user_id'] == user_id) | 
            (self.messages_df['request_id'] == request_id)
        ]

        for _, row in user_msgs.iterrows():
            text = str(row['message_text']).strip()
            if self.is_prompt_injection(text):
                # Reject prompt injection entirely; treat as hostile payload
                continue

            source = str(row['source_type']).strip().lower()
            evt_id = str(row['related_event_id']).strip() if pd.notna(row['related_event_id']) else None

            # 1. Employer messages
            if source == 'employer':
                # Seasonal contract ended
                if "contract has ended" in text.lower() or "no off-season income" in text.lower():
                    facts["salary_ended"] = True

                # Salary raise / increase
                # English: "monthly salary has increased to USD 2988. The change applies from 2026-07-15"
                # Indonesian: "Gaji bulanan Anda naik menjadi IDR 42750000. Perubahan ini berlaku mulai 2025-08-15."
                m_inc = re.search(r"(?:naik\s+menjadi|increased\s+to)\s+[A-Z]{3}\s+([\d,\.]+).*?(?:mulai|from)\s+(\d{4}-\d{2}-\d{2})", text, re.I)
                if m_inc:
                    amt = float(m_inc.group(1).replace(',', '').rstrip('.'))
                    dt = m_inc.group(2)
                    facts["salary_override"] = {"amount": amt, "effective_date": dt}

                # Temporary monthly pay / reduced amount
                # "Your temporary monthly pay is EUR 1037.52. The reduced amount continues"
                m_temp = re.search(r"(?:temporary\s+monthly\s+pay\s+is|next\s+salary\s+is\s+reduced\s+to)\s+[A-Z]{3}\s+([\d,\.]+)", text, re.I)
                if m_temp:
                    amt = float(m_temp.group(1).replace(',', '').rstrip('.'))
                    facts["salary_reduced"] = amt

                # Salary date change
                # "confirmed salary is now expected on 2024-09-23. This replaces the payroll date"
                m_date = re.search(r"(?:expected\s+on|dikonfirmasi.*?pada)\s+(\d{4}-\d{2}-\d{2})", text, re.I)
                if m_date and "replaces" in text.lower():
                    facts["salary_date_override"] = m_date.group(1)

                # First salary
                # "Your first salary will be EUR 1661. The confirmed credit date is 2026-01-15."
                # "first salary will be ZAR 54120. The confirmed credit date is 2025-02-15."
                m_first = re.search(r"first\s+salary\s+will\s+be\s+[A-Z]{3}\s+([\d,\.]+).*?date\s+is\s+(\d{4}-\d{2}-\d{2})", text, re.I)
                if m_first:
                    amt = float(m_first.group(1).replace(',', '').rstrip('.'))
                    dt = m_first.group(2)
                    facts["salary_first"] = {"amount": amt, "credit_date": dt}

                # Arrears adjustment
                # "one-time arrears adjustment of EUR 653.40"
                # "penyesuaian tunggakan satu kali sebesar IDR 9490500"
                m_arr = re.search(r"(?:arrears\s+adjustment\s+of|tunggakan.*?sebesar)\s+[A-Z]{3}\s+([\d,\.]+)", text, re.I)
                if m_arr:
                    amt = float(m_arr.group(1).replace(',', '').rstrip('.'))
                    facts["arrears_adjustment"] = amt

                # One household employment record ended
                # "The remaining confirmed monthly salary is INR 148000."
                m_rem = re.search(r"remaining\s+confirmed\s+monthly\s+salary\s+is\s+[A-Z]{3}\s+([\d,\.]+)", text, re.I)
                if m_rem:
                    amt = float(m_rem.group(1).replace(',', '').rstrip('.'))
                    facts["salary_override"] = {"amount": amt, "effective_date": "2000-01-01"}

            # 2. Service provider messages
            elif source == 'service_provider':
                # Rent increase: "The renewed lease increases monthly rent by 12%"
                m_rent = re.search(r"increases\s+monthly\s+rent\s+by\s+(\d+)%", text, re.I)
                if m_rent:
                    facts["rent_increase_pct"] = float(m_rent.group(1)) / 100.0

                # Confirmed invoice payment: "approved an invoice payment of INR 196000. Settlement is expected on 2024-12-15"
                # "menyetujui pembayaran faktur sebesar IDR 30780000. Penyelesaian diperkirakan pada 2025-08-15"
                m_inv = re.search(r"(?:invoice\s+payment\s+of|pembayaran\s+faktur\s+sebesar)\s+[A-Z]{3}\s+([\d,\.]+).*?(?:expected\s+on|pada)\s+(\d{4}-\d{2}-\d{2})", text, re.I)
                if m_inv:
                    amt = float(m_inv.group(1).replace(',', '').rstrip('.'))
                    dt = m_inv.group(2)
                    facts["confirmed_invoices"].append({"amount": amt, "settlement_date": dt})


            # 3. Bank / Merchant / Financial Service
            if evt_id:
                if "transfer between your two accounts" in text.lower():
                    facts["internal_transfers"].add(evt_id)
                if "has not reached your account yet" in text.lower() or "still in payment processing" in text.lower():
                    facts["pending_credits_to_ignore"].add(evt_id)
                if "no cash proceeds have been generated" in text.lower() or "unrealized" in text.lower():
                    facts["unrealized_investments"].add(evt_id)

        return facts
