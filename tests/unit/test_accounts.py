"""Unit tests for services/accounts.py.

Tests use tmp_path to avoid touching profile/accounts.json.
All monetary comparisons use Decimal.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from services.accounts import (
    AccountIn,
    AccountOut,
    HoldingIn,
    create_account,
    create_holding,
    delete_account,
    delete_holding,
    get_account,
    get_portfolio_summary,
    load_accounts,
    update_account,
    update_holding,
)


def dec(s: str) -> Decimal:
    return Decimal(s)


def _db(tmp_path: Path) -> Path:
    return tmp_path / "accounts.json"


# ---------------------------------------------------------------------------
# Account CRUD — all four types
# ---------------------------------------------------------------------------

class TestCreateAccount:
    def test_creates_taxable(self, tmp_path):
        result = create_account(
            AccountIn(name="Vanguard Brokerage", account_type="taxable"),
            _path=_db(tmp_path),
        )
        assert result.account_type == "taxable"
        assert result.name == "Vanguard Brokerage"
        assert result.id  # non-empty uuid
        assert result.holdings == []
        assert result.total_value == dec("0")
        assert result.total_basis == dec("0")
        assert result.total_unrealized_gain == dec("0")
        assert result.balance is None
        assert result.annual_contribution is None

    def test_creates_traditional(self, tmp_path):
        result = create_account(
            AccountIn(name="Rollover IRA", account_type="traditional", balance=dec("250000")),
            _path=_db(tmp_path),
        )
        assert result.account_type == "traditional"
        assert result.balance == dec("250000")
        assert result.holdings is None
        assert result.total_value is None

    def test_creates_roth(self, tmp_path):
        result = create_account(
            AccountIn(name="Roth IRA", account_type="roth", balance=dec("80000")),
            _path=_db(tmp_path),
        )
        assert result.account_type == "roth"
        assert result.balance == dec("80000")

    def test_creates_hsa(self, tmp_path):
        result = create_account(
            AccountIn(
                name="HSA",
                account_type="hsa",
                balance=dec("15000"),
                annual_contribution=dec("4300"),
            ),
            _path=_db(tmp_path),
        )
        assert result.account_type == "hsa"
        assert result.balance == dec("15000")
        assert result.annual_contribution == dec("4300")

    def test_persists_to_file(self, tmp_path):
        db = _db(tmp_path)
        create_account(AccountIn(name="A", account_type="roth", balance=dec("1000")), _path=db)
        accounts = load_accounts(_path=db)
        assert len(accounts) == 1
        assert accounts[0].name == "A"

    def test_each_account_gets_unique_id(self, tmp_path):
        db = _db(tmp_path)
        a = create_account(AccountIn(name="A", account_type="roth", balance=dec("1")), _path=db)
        b = create_account(AccountIn(name="B", account_type="roth", balance=dec("2")), _path=db)
        assert a.id != b.id


class TestGetAccount:
    def test_returns_existing_account(self, tmp_path):
        db = _db(tmp_path)
        created = create_account(
            AccountIn(name="IRA", account_type="traditional", balance=dec("50000")),
            _path=db,
        )
        fetched = get_account(created.id, _path=db)
        assert fetched.id == created.id
        assert fetched.balance == dec("50000")

    def test_raises_for_missing_account(self, tmp_path):
        with pytest.raises(ValueError, match="Account not found"):
            get_account("nonexistent-id", _path=_db(tmp_path))


class TestUpdateAccount:
    def test_updates_name_and_balance(self, tmp_path):
        db = _db(tmp_path)
        created = create_account(
            AccountIn(name="Old Name", account_type="traditional", balance=dec("100000")),
            _path=db,
        )
        updated = update_account(
            created.id,
            AccountIn(name="New Name", account_type="traditional", balance=dec("120000")),
            _path=db,
        )
        assert updated.id == created.id
        assert updated.name == "New Name"
        assert updated.balance == dec("120000")

    def test_preserves_holdings_on_taxable_rename(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="Brokerage", account_type="taxable"), _path=db)
        create_holding(acct.id, HoldingIn(ticker="AAPL", basis=dec("1000"), value=dec("1500")), _path=db)
        updated = update_account(
            acct.id,
            AccountIn(name="Renamed Brokerage", account_type="taxable"),
            _path=db,
        )
        assert len(updated.holdings or []) == 1

    def test_raises_for_missing_account(self, tmp_path):
        with pytest.raises(ValueError, match="Account not found"):
            update_account(
                "bad-id",
                AccountIn(name="X", account_type="roth", balance=dec("0")),
                _path=_db(tmp_path),
            )


class TestDeleteAccount:
    def test_deletes_account(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="Del", account_type="roth", balance=dec("1")), _path=db)
        delete_account(acct.id, _path=db)
        assert load_accounts(_path=db) == []

    def test_raises_for_missing_account(self, tmp_path):
        with pytest.raises(ValueError, match="Account not found"):
            delete_account("no-such-id", _path=_db(tmp_path))


# ---------------------------------------------------------------------------
# Holding derived values
# ---------------------------------------------------------------------------

class TestHoldingDerivedValues:
    def test_unrealized_gain_positive(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="B", account_type="taxable"), _path=db)
        result = create_holding(
            acct.id,
            HoldingIn(ticker="AAPL", basis=dec("10000"), value=dec("15000")),
            _path=db,
        )
        h = result.holdings[0]
        assert h.unrealized_gain == dec("5000")

    def test_unrealized_gain_negative(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="B", account_type="taxable"), _path=db)
        result = create_holding(
            acct.id,
            HoldingIn(ticker="COIN", basis=dec("20000"), value=dec("12000")),
            _path=db,
        )
        h = result.holdings[0]
        assert h.unrealized_gain == dec("-8000")

    def test_unrealized_gain_zero(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="B", account_type="taxable"), _path=db)
        result = create_holding(
            acct.id,
            HoldingIn(ticker="VTI", basis=dec("5000"), value=dec("5000")),
            _path=db,
        )
        assert result.holdings[0].unrealized_gain == dec("0")

    def test_ticker_stored_uppercase(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="B", account_type="taxable"), _path=db)
        result = create_holding(
            acct.id,
            HoldingIn(ticker="aapl", basis=dec("100"), value=dec("110")),
            _path=db,
        )
        assert result.holdings[0].ticker == "AAPL"


# ---------------------------------------------------------------------------
# Account derived totals (taxable)
# ---------------------------------------------------------------------------

class TestAccountDerivedTotals:
    def test_totals_sum_across_holdings(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="B", account_type="taxable"), _path=db)
        create_holding(acct.id, HoldingIn(ticker="A", basis=dec("1000"), value=dec("2000")), _path=db)
        result = create_holding(
            acct.id, HoldingIn(ticker="B", basis=dec("3000"), value=dec("3500")), _path=db
        )
        assert result.total_basis == dec("4000")
        assert result.total_value == dec("5500")
        assert result.total_unrealized_gain == dec("1500")

    def test_totals_zero_with_no_holdings(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="B", account_type="taxable"), _path=db)
        assert acct.total_basis == dec("0")
        assert acct.total_value == dec("0")
        assert acct.total_unrealized_gain == dec("0")

    def test_totals_none_for_non_taxable(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(
            AccountIn(name="IRA", account_type="traditional", balance=dec("50000")), _path=db
        )
        assert acct.total_basis is None
        assert acct.total_value is None
        assert acct.total_unrealized_gain is None


# ---------------------------------------------------------------------------
# Holding CRUD
# ---------------------------------------------------------------------------

class TestHoldingCRUD:
    def test_create_holding_returns_updated_account(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="B", account_type="taxable"), _path=db)
        result = create_holding(
            acct.id, HoldingIn(ticker="VTI", basis=dec("5000"), value=dec("6000")), _path=db
        )
        assert isinstance(result, AccountOut)
        assert len(result.holdings) == 1
        assert result.holdings[0].ticker == "VTI"

    def test_update_holding(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="B", account_type="taxable"), _path=db)
        with_holding = create_holding(
            acct.id, HoldingIn(ticker="VTI", basis=dec("5000"), value=dec("6000")), _path=db
        )
        hid = with_holding.holdings[0].id
        result = update_holding(
            acct.id, hid, HoldingIn(ticker="VTI", basis=dec("5000"), value=dec("7000")), _path=db
        )
        assert result.holdings[0].value == dec("7000")
        assert result.holdings[0].unrealized_gain == dec("2000")

    def test_delete_holding(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="B", account_type="taxable"), _path=db)
        with_holding = create_holding(
            acct.id, HoldingIn(ticker="VTI", basis=dec("5000"), value=dec("6000")), _path=db
        )
        hid = with_holding.holdings[0].id
        result = delete_holding(acct.id, hid, _path=db)
        assert result.holdings == []
        assert result.total_value == dec("0")

    def test_create_holding_on_non_taxable_raises(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(
            AccountIn(name="IRA", account_type="traditional", balance=dec("50000")), _path=db
        )
        with pytest.raises(ValueError):
            create_holding(acct.id, HoldingIn(ticker="VTI", basis=dec("100"), value=dec("110")), _path=db)

    def test_update_holding_wrong_account_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Account not found"):
            update_holding("bad-acct", "bad-hold", HoldingIn(ticker="X", basis=dec("1"), value=dec("1")), _path=_db(tmp_path))

    def test_update_holding_wrong_holding_raises(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="B", account_type="taxable"), _path=db)
        with pytest.raises(ValueError, match="Holding not found"):
            update_holding(acct.id, "no-such-holding", HoldingIn(ticker="X", basis=dec("1"), value=dec("1")), _path=db)

    def test_delete_holding_wrong_holding_raises(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="B", account_type="taxable"), _path=db)
        with pytest.raises(ValueError, match="Holding not found"):
            delete_holding(acct.id, "no-such-holding", _path=db)


# ---------------------------------------------------------------------------
# Portfolio summary
# ---------------------------------------------------------------------------

class TestPortfolioSummary:
    def test_empty_portfolio(self, tmp_path):
        summary = get_portfolio_summary(_path=_db(tmp_path))
        assert summary.taxable_value == dec("0")
        assert summary.traditional_balance == dec("0")
        assert summary.roth_balance == dec("0")
        assert summary.hsa_balance == dec("0")
        assert summary.total_portfolio_value == dec("0")

    def test_aggregates_all_types(self, tmp_path):
        db = _db(tmp_path)
        taxable = create_account(AccountIn(name="Brokerage", account_type="taxable"), _path=db)
        create_holding(taxable.id, HoldingIn(ticker="VTI", basis=dec("10000"), value=dec("15000")), _path=db)
        create_account(AccountIn(name="IRA", account_type="traditional", balance=dec("200000")), _path=db)
        create_account(AccountIn(name="Roth", account_type="roth", balance=dec("80000")), _path=db)
        create_account(AccountIn(name="HSA", account_type="hsa", balance=dec("20000"), annual_contribution=dec("4300")), _path=db)

        summary = get_portfolio_summary(_path=db)
        assert summary.taxable_value == dec("15000")
        assert summary.taxable_basis == dec("10000")
        assert summary.taxable_unrealized_gain == dec("5000")
        assert summary.traditional_balance == dec("200000")
        assert summary.roth_balance == dec("80000")
        assert summary.hsa_balance == dec("20000")
        assert summary.hsa_annual_contribution == dec("4300")
        assert summary.total_portfolio_value == dec("315000")

    def test_multiple_taxable_accounts_summed(self, tmp_path):
        db = _db(tmp_path)
        for name in ("Brokerage A", "Brokerage B"):
            acct = create_account(AccountIn(name=name, account_type="taxable"), _path=db)
            create_holding(acct.id, HoldingIn(ticker="VTI", basis=dec("5000"), value=dec("8000")), _path=db)
        summary = get_portfolio_summary(_path=db)
        assert summary.taxable_value == dec("16000")
        assert summary.taxable_basis == dec("10000")

    def test_total_portfolio_value_excludes_unrealized_gain_double_count(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="B", account_type="taxable"), _path=db)
        create_holding(acct.id, HoldingIn(ticker="VTI", basis=dec("1000"), value=dec("2000")), _path=db)
        create_account(AccountIn(name="IRA", account_type="traditional", balance=dec("3000")), _path=db)
        summary = get_portfolio_summary(_path=db)
        assert summary.total_portfolio_value == dec("5000")


# ---------------------------------------------------------------------------
# HSA annual_contribution
# ---------------------------------------------------------------------------

class TestHsaAnnualContribution:
    def test_hsa_contribution_stored_and_returned(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(
            AccountIn(name="HSA", account_type="hsa", balance=dec("10000"), annual_contribution=dec("4300")),
            _path=db,
        )
        assert acct.annual_contribution == dec("4300")
        fetched = get_account(acct.id, _path=db)
        assert fetched.annual_contribution == dec("4300")

    def test_hsa_without_contribution_is_none(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(
            AccountIn(name="HSA", account_type="hsa", balance=dec("5000")), _path=db
        )
        assert acct.annual_contribution is None

    def test_hsa_contribution_in_summary(self, tmp_path):
        db = _db(tmp_path)
        create_account(AccountIn(name="HSA1", account_type="hsa", balance=dec("1000"), annual_contribution=dec("2000")), _path=db)
        create_account(AccountIn(name="HSA2", account_type="hsa", balance=dec("500"), annual_contribution=dec("1000")), _path=db)
        summary = get_portfolio_summary(_path=db)
        assert summary.hsa_annual_contribution == dec("3000")


# ---------------------------------------------------------------------------
# Multiple entries for same ticker handled independently
# ---------------------------------------------------------------------------

class TestDuplicateTicker:
    def test_same_ticker_two_independent_holdings(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="B", account_type="taxable"), _path=db)
        create_holding(acct.id, HoldingIn(ticker="AAPL", basis=dec("1000"), value=dec("1500")), _path=db)
        result = create_holding(acct.id, HoldingIn(ticker="AAPL", basis=dec("2000"), value=dec("2200")), _path=db)
        assert len(result.holdings) == 2
        ids = {h.id for h in result.holdings}
        assert len(ids) == 2  # distinct ids

    def test_deleting_one_same_ticker_leaves_the_other(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="B", account_type="taxable"), _path=db)
        h1_acct = create_holding(acct.id, HoldingIn(ticker="AAPL", basis=dec("1000"), value=dec("1500")), _path=db)
        h1_id = h1_acct.holdings[0].id
        create_holding(acct.id, HoldingIn(ticker="AAPL", basis=dec("2000"), value=dec("2200")), _path=db)
        result = delete_holding(acct.id, h1_id, _path=db)
        assert len(result.holdings) == 1
        assert result.holdings[0].basis == dec("2000")

    def test_updating_one_same_ticker_does_not_affect_other(self, tmp_path):
        db = _db(tmp_path)
        acct = create_account(AccountIn(name="B", account_type="taxable"), _path=db)
        h1_acct = create_holding(acct.id, HoldingIn(ticker="AAPL", basis=dec("1000"), value=dec("1500")), _path=db)
        h1_id = h1_acct.holdings[0].id
        create_holding(acct.id, HoldingIn(ticker="AAPL", basis=dec("2000"), value=dec("2200")), _path=db)
        result = update_holding(acct.id, h1_id, HoldingIn(ticker="AAPL", basis=dec("1000"), value=dec("9999")), _path=db)
        values = {h.id: h.value for h in result.holdings}
        assert values[h1_id] == dec("9999")
        other_id = next(hid for hid in values if hid != h1_id)
        assert values[other_id] == dec("2200")
