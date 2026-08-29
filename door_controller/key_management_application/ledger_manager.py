import datetime

DEFAULT_ACCOUNTS = [
    {"name": "Assets:Checking", "type": "Asset", "description": "HOA Primary Checking Operating Account"},
    {"name": "Assets:Investment", "type": "Asset", "description": "HOA Reserve Investment Account"},
    {"name": "Liabilities:Escrow:ClubhouseSecurityDeposits", "type": "Liability", "description": "Escrow Liability for Clubhouse Security Deposits"},
    {"name": "Income:ClubhouseRentalFees", "type": "Income", "description": "Rental Fees Received for Clubhouse Use"},
    {"name": "Income:HOADues", "type": "Income", "description": "HOA Member Dues & Assessments"},
    {"name": "Income:InvestmentReturns", "type": "Income", "description": "Dividends & Interest Earned on Reserve Account"},
    {"name": "Expenses:Maintenance", "type": "Expense", "description": "Clubhouse & Grounds Maintenance Expenses"},
    {"name": "Expenses:Utilities", "type": "Expense", "description": "Water, Gas, Electricity, Internet Utilities"},
    {"name": "Expenses:Operations", "type": "Expense", "description": "Administrative & Operational Expenses"}
]

class Posting:
    def __init__(self, account_name, amount, commodity="USD"):
        self.account_name = str(account_name).strip()
        self.amount = float(amount)
        self.commodity = commodity

    def to_dict(self):
        return {
            "account_name": self.account_name,
            "amount": self.amount,
            "commodity": self.commodity
        }

class Transaction:
    def __init__(self, payee, postings, date=None, notes=None, tx_id=None):
        self.tx_id = tx_id
        self.payee = str(payee).strip()
        self.notes = notes or ""
        
        if isinstance(date, str):
            try:
                self.date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                self.date = datetime.date.today()
        elif isinstance(date, (datetime.date, datetime.datetime)):
            self.date = date if isinstance(date, datetime.date) else date.date()
        else:
            self.date = datetime.date.today()

        self.postings = []
        for p in postings:
            if isinstance(p, Posting):
                self.postings.append(p)
            elif isinstance(p, dict):
                self.postings.append(Posting(p.get("account_name"), p.get("amount"), p.get("commodity", "USD")))

        self.validate()

    def validate(self):
        if len(self.postings) < 2:
            raise ValueError("A double-entry transaction requires at least 2 postings.")
        total_sum = sum(round(p.amount, 4) for p in self.postings)
        if abs(total_sum) > 1e-4:
            raise ValueError(f"Unbalanced transaction: Sum of postings must be zero (Sum={total_sum:.4f}).")

    def to_dict(self):
        return {
            "tx_id": self.tx_id,
            "date": self.date.strftime("%Y-%m-%d"),
            "payee": self.payee,
            "notes": self.notes,
            "postings": [p.to_dict() for p in self.postings]
        }

class LedgerEngine:
    """
    Simplified double-entry ledger engine inspired by ledger.py.
    Tracks multiple accounts (Checking, Investment, Escrow, Income, Expenses).
    """
    def __init__(self):
        self.transactions = []
        self.account_definitions = {acc["name"]: acc for acc in DEFAULT_ACCOUNTS}

    def add_transaction(self, tx):
        if not isinstance(tx, Transaction):
            tx = Transaction(payee=tx.get("payee"), postings=tx.get("postings"), date=tx.get("date"), notes=tx.get("notes"), tx_id=tx.get("tx_id"))
        self.transactions.append(tx)
        return tx

    def get_account_balances(self):
        """
        Calculates current balance for all accounts based on recorded transactions.
        """
        balances = {acc_name: 0.0 for acc_name in self.account_definitions}

        for tx in self.transactions:
            for p in tx.postings:
                acc = p.account_name
                if acc not in balances:
                    balances[acc] = 0.0
                balances[acc] += p.amount

        return balances

    def get_financial_summary(self):
        """
        Returns summary metrics:
          - checking_balance: Assets:Checking
          - investment_balance: Assets:Investment
          - escrow_balance: Liabilities:Escrow:ClubhouseSecurityDeposits
          - total_income: Sum of all Income:* credits (negated for display as positive)
          - total_expenses: Sum of all Expenses:* debits
          - net_assets: Assets - Liabilities
        """
        balances = self.get_account_balances()
        
        checking = balances.get("Assets:Checking", 0.0)
        investment = balances.get("Assets:Investment", 0.0)
        escrow = balances.get("Liabilities:Escrow:ClubhouseSecurityDeposits", 0.0)

        # In double-entry accounting:
        # Asset debits are (+), credits are (-)
        # Liability credits are (+), debits are (-)
        # Income credits are (-), debits are (+)
        # Expense debits are (+), credits are (-)

        total_income = sum(-val for acc, val in balances.items() if acc.startswith("Income:"))
        total_expenses = sum(val for acc, val in balances.items() if acc.startswith("Expenses:"))
        total_assets = sum(val for acc, val in balances.items() if acc.startswith("Assets:"))
        total_liabilities = sum(val for acc, val in balances.items() if acc.startswith("Liabilities:"))

        return {
            "checking_balance": checking,
            "investment_balance": investment,
            "escrow_balance": abs(escrow),
            "total_income": total_income,
            "total_expenses": total_expenses,
            "total_assets": total_assets,
            "total_liabilities": abs(total_liabilities),
            "net_assets": total_assets - abs(total_liabilities)
        }

    def export_ledger_journal(self):
        """
        Exports transaction entries in standard Ledger CLI journal format.
        """
        lines = []
        for tx in self.transactions:
            date_str = tx.date.strftime("%Y/%m/%d")
            lines.append(f"{date_str} {tx.payee}")
            for p in tx.postings:
                amt_str = f"${p.amount:,.2f}"
                lines.append(f"    {p.account_name:<45} {amt_str:>15}")
            lines.append("")
        return "\n".join(lines)
