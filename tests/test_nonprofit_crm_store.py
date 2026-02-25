from __future__ import annotations

from datetime import date

import pytest

from nonprofit_crm.store import CRMStore


def _build_store(tmp_path) -> CRMStore:  # type: ignore[no-untyped-def]
    db_path = tmp_path / "nonprofit_crm_test.db"
    store = CRMStore(db_path)
    store.init_db()
    return store


def test_add_donor_validates_required_fields(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = _build_store(tmp_path)

    with pytest.raises(ValueError):
        store.add_donor(
            donor_type="Individual",
            first_name="",
            last_name="",
            organization_name=None,
            email=None,
            phone=None,
            lifecycle_stage="Prospect",
            relationship_manager=None,
            preferred_channel=None,
            notes=None,
        )

    with pytest.raises(ValueError):
        store.add_donor(
            donor_type="Organization",
            first_name=None,
            last_name=None,
            organization_name="",
            email=None,
            phone=None,
            lifecycle_stage="Prospect",
            relationship_manager=None,
            preferred_channel=None,
            notes=None,
        )

    donor_id = store.add_donor(
        donor_type="Individual",
        first_name="Avery",
        last_name="Mills",
        organization_name=None,
        email="avery@example.org",
        phone="555-0101",
        lifecycle_stage="Active",
        relationship_manager="Morgan",
        preferred_channel="Email",
        notes="",
    )
    org_id = store.add_donor(
        donor_type="Organization",
        first_name=None,
        last_name=None,
        organization_name="Community Builders Foundation",
        email="grants@cbf.org",
        phone="555-0102",
        lifecycle_stage="Foundation",
        relationship_manager="Jordan",
        preferred_channel="Email",
        notes=None,
    )

    all_donors = store.list_donors()
    ids = {row["id"] for row in all_donors}
    assert donor_id in ids
    assert org_id in ids


def test_smart_search_matches_name_variants(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = _build_store(tmp_path)

    nick_id = store.add_donor(
        donor_type="Individual",
        first_name="Nick",
        last_name="Harrison",
        organization_name=None,
        email="nick.h@example.org",
        phone="555-2200",
        lifecycle_stage="Active",
        relationship_manager="Morgan",
        preferred_channel="Email",
        notes=None,
    )
    store.add_donor(
        donor_type="Individual",
        first_name="Nicole",
        last_name="Sanders",
        organization_name=None,
        email="nicole@example.org",
        phone="555-2201",
        lifecycle_stage="Prospect",
        relationship_manager=None,
        preferred_channel="Email",
        notes=None,
    )

    default_matches = store.list_donors(search_term="Nicholas")
    assert all(row["id"] != nick_id for row in default_matches)

    smart_matches = store.list_donors(search_term="Nicholas", smart_search=True)
    assert any(row["id"] == nick_id for row in smart_matches)


def test_reconciliation_snapshot_tracks_linked_records(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = _build_store(tmp_path)

    donor_id = store.add_donor(
        donor_type="Individual",
        first_name="River",
        last_name="Lane",
        organization_name=None,
        email="river@example.org",
        phone=None,
        lifecycle_stage="Active",
        relationship_manager=None,
        preferred_channel="Email",
        notes=None,
    )

    bank_account_id = store.list_bank_accounts()[0]["id"]
    ledger_entry_id = store.add_ledger_entry(
        posted_date=date(2026, 2, 10),
        account_code="4000-DONATIONS",
        description="Donation income",
        amount_cents=12500,
        reference_code="D-100",
        source="Manual",
    )
    donation_id = store.add_donation(
        donor_id=donor_id,
        donation_date=date(2026, 2, 10),
        amount_cents=12500,
        donation_type="One-time",
        campaign="Winter Appeal",
        fund="General",
        payment_method="ACH",
        reference_code="D-100",
        bank_account_id=bank_account_id,
        ledger_entry_id=ledger_entry_id,
        notes=None,
        is_anonymous=False,
    )
    bank_tx_id = store.add_bank_transaction(
        bank_account_id=bank_account_id,
        transaction_date=date(2026, 2, 11),
        description="Donor ACH",
        amount_cents=12500,
        reference_code="D-100",
    )

    store.match_donation_to_bank_transaction(
        donation_id=donation_id,
        bank_transaction_id=bank_tx_id,
    )

    snapshot = store.reconciliation_snapshot(
        bank_account_id=bank_account_id,
        month_start=date(2026, 2, 1),
        month_end=date(2026, 2, 28),
    )

    assert snapshot["donation_count"] == 1
    assert snapshot["donation_total_cents"] == 12500
    assert snapshot["bank_total_cents"] == 12500
    assert snapshot["fully_reconciled_count"] == 1
    assert snapshot["variance_cents"] == 0
    assert snapshot["missing_bank_count"] == 0
    assert snapshot["missing_ledger_count"] == 0
    assert snapshot["completion_percent"] == 100.0


def test_auto_match_by_reference_matches_only_exact_candidates(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = _build_store(tmp_path)

    donor_id = store.add_donor(
        donor_type="Individual",
        first_name="Sam",
        last_name="Ng",
        organization_name=None,
        email=None,
        phone=None,
        lifecycle_stage="Active",
        relationship_manager=None,
        preferred_channel="Email",
        notes=None,
    )
    bank_account_id = store.list_bank_accounts()[0]["id"]

    store.add_donation(
        donor_id=donor_id,
        donation_date=date(2026, 2, 1),
        amount_cents=10000,
        donation_type="One-time",
        campaign=None,
        fund=None,
        payment_method="ACH",
        reference_code="REF-1",
        bank_account_id=bank_account_id,
        ledger_entry_id=None,
        notes=None,
    )
    store.add_donation(
        donor_id=donor_id,
        donation_date=date(2026, 2, 2),
        amount_cents=9000,
        donation_type="One-time",
        campaign=None,
        fund=None,
        payment_method="ACH",
        reference_code="REF-2",
        bank_account_id=bank_account_id,
        ledger_entry_id=None,
        notes=None,
    )

    store.add_bank_transaction(
        bank_account_id=bank_account_id,
        transaction_date=date(2026, 2, 3),
        description="Matched donation",
        amount_cents=10000,
        reference_code="REF-1",
    )
    store.add_bank_transaction(
        bank_account_id=bank_account_id,
        transaction_date=date(2026, 2, 4),
        description="Mismatched amount",
        amount_cents=8500,
        reference_code="REF-2",
    )

    matched = store.auto_match_by_reference(
        bank_account_id=bank_account_id,
        month_start=date(2026, 2, 1),
        month_end=date(2026, 2, 28),
    )

    assert matched == 1
    still_unmatched = store.donations_missing_bank_match(
        bank_account_id=bank_account_id,
        month_start=date(2026, 2, 1),
        month_end=date(2026, 2, 28),
    )
    assert len(still_unmatched) == 1
    assert still_unmatched[0]["reference_code"] == "REF-2"


def test_campaign_rollup_and_opportunity_stage_updates(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = _build_store(tmp_path)

    donor_id = store.add_donor(
        donor_type="Individual",
        first_name="Kai",
        last_name="Parker",
        organization_name=None,
        email="kai@example.org",
        phone=None,
        lifecycle_stage="Prospect",
        relationship_manager="Lee",
        preferred_channel="Email",
        notes=None,
    )

    campaign_id = store.add_campaign(
        name="Spring Gala 2026",
        campaign_type="Event",
        status="In Progress",
        owner="Lee",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        goal_cents=500000,
        parent_campaign_id=None,
        description="Annual spring gala campaign",
    )

    donation_id = store.add_donation(
        donor_id=donor_id,
        donation_date=date(2026, 3, 10),
        amount_cents=25000,
        donation_type="One-time",
        campaign=None,
        fund="General",
        payment_method="Check",
        reference_code="GAL-100",
        bank_account_id=None,
        ledger_entry_id=None,
        notes=None,
        opportunity_name="Kai Parker - Gala Gift",
        opportunity_stage="Prospecting",
        close_date=date(2026, 3, 20),
        campaign_id=campaign_id,
        probability_percent=35,
    )

    campaigns = store.list_campaigns(active_only=False)
    spring_campaign = next(row for row in campaigns if row["id"] == campaign_id)
    assert spring_campaign["gift_count"] == 1
    assert spring_campaign["raised_cents"] == 25000

    pipeline_before = {row["stage_name"]: row for row in store.opportunity_pipeline()}
    assert pipeline_before["Prospecting"]["opportunity_count"] == 1
    assert pipeline_before["Prospecting"]["total_cents"] == 25000

    store.update_opportunity_stage(
        donation_id=donation_id,
        stage_name="Closed Won",
        probability_percent=100,
    )

    closed_won = store.list_donations(opportunity_stage="Closed Won")
    assert any(row["id"] == donation_id for row in closed_won)
