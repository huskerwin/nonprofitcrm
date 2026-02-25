from __future__ import annotations

from datetime import date

from nonprofit_crm.hipaa_scan import HipaaSensitivityScanner
from nonprofit_crm.store import CRMStore


def _build_store(tmp_path) -> CRMStore:  # type: ignore[no-untyped-def]
    db_path = tmp_path / "hipaa_scan_test.db"
    store = CRMStore(db_path)
    store.init_db()
    return store


def test_scanner_flags_ssn_and_dob_context() -> None:
    scanner = HipaaSensitivityScanner()
    records = [
        {
            "object_name": "Engagement Plans",
            "table_name": "engagements",
            "record_id": 42,
            "fields": {
                "summary": "Patient follow-up scheduled. DOB: 01/19/1988. SSN 123-45-6789 was provided.",
            },
        }
    ]

    findings = scanner.scan_records(records)
    signals = {row["signal"] for row in findings}

    assert "SSN" in signals
    assert "Date of Birth" in signals
    assert any(row["severity"] == "High" for row in findings)


def test_scanner_flags_medical_context_with_identifier() -> None:
    scanner = HipaaSensitivityScanner()
    records = [
        {
            "object_name": "Accounts & Contacts",
            "table_name": "donors",
            "record_id": 7,
            "fields": {
                "notes": "Discussed spinal injury treatment plan with patient. Contact jane@example.org for updates.",
            },
        }
    ]

    findings = scanner.scan_records(records)
    assert any(row["signal"] == "Medical Context + Identifier" for row in findings)


def test_scanner_ignores_normal_contact_data_without_medical_context() -> None:
    scanner = HipaaSensitivityScanner()
    records = [
        {
            "object_name": "Accounts & Contacts",
            "table_name": "donors",
            "record_id": 9,
            "fields": {
                "first_name": "Nick",
                "last_name": "Harrison",
                "email": "nick@example.org",
                "phone": "555-2200",
            },
        }
    ]

    findings = scanner.scan_records(records)
    assert findings == []


def test_store_records_for_hipaa_scan_includes_core_objects(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = _build_store(tmp_path)

    donor_id = store.add_donor(
        donor_type="Individual",
        first_name="Casey",
        last_name="Miller",
        organization_name=None,
        email="casey@example.org",
        phone="555-0199",
        lifecycle_stage="Active",
        relationship_manager="A. Jordan",
        preferred_channel="Email",
        notes="DOB 1988-01-19 from intake form",
    )
    store.add_engagement(
        donor_id=donor_id,
        engagement_date=date(2026, 2, 18),
        engagement_type="Meeting",
        channel="In Person",
        summary="Patient requested referral support",
        next_step="",
        follow_up_date=None,
        owner="A. Jordan",
    )
    store.add_campaign(
        name="Recovery Outreach",
        campaign_type="Fundraising",
        status="In Progress",
        owner="A. Jordan",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 3, 1),
        goal_cents=200000,
        parent_campaign_id=None,
        description="Support rehabilitation services",
    )

    records = store.records_for_hipaa_scan()
    tables = {row["table_name"] for row in records}

    assert "donors" in tables
    assert "engagements" in tables
    assert "campaigns" in tables
