# CRM Architecture and Runtime Flow

This document explains how the nonprofit CRM works end to end.

## High-level architecture

The CRM is a Streamlit application backed by a SQLite persistence layer and optional AI-assisted compliance review.

```mermaid
flowchart LR
    user["Fundraising / Finance User"] --> ui["Streamlit UI<br/>nonprofit_crm_app.py"]
    ui --> store["CRMStore service layer<br/>nonprofit_crm/store.py"]
    store --> db[("SQLite database<br/>.data/nonprofit_crm.db")]
    ui --> scanner["HIPAA sensitivity scanner<br/>nonprofit_crm/hipaa_scan.py"]
    scanner --> store
    ui --> export["CSV exports and operational reports"]
```

## Core business flows

### Relationship and gift lifecycle

```mermaid
sequenceDiagram
    actor User
    participant UI as Streamlit UI
    participant Store as CRMStore
    participant DB as SQLite

    User->>UI: Create account/contact
    UI->>Store: add_donor(...)
    Store->>DB: INSERT donors

    User->>UI: Log engagement task/activity
    UI->>Store: add_engagement(...)
    Store->>DB: INSERT engagements

    User->>UI: Create opportunity
    UI->>Store: add_donation(...)
    Store->>DB: INSERT donations

    User->>UI: Update stage/probability
    UI->>Store: update_opportunity_stage(...)
    Store->>DB: UPDATE donations

    User->>UI: Link gift to ledger and bank transaction
    UI->>Store: link_donation_to_ledger(...)
    UI->>Store: match_donation_to_bank_transaction(...)
    Store->>DB: UPDATE donations / bank_transactions
```

### Monthly reconciliation

```mermaid
sequenceDiagram
    actor Finance
    participant UI as Reconciliation Tab
    participant Store as CRMStore
    participant DB as SQLite

    Finance->>UI: Select bank account + month
    UI->>Store: reconciliation_snapshot(...)
    Store->>DB: Aggregate donations and bank transactions
    Store-->>UI: Totals, variance, completion metrics

    Finance->>UI: Auto-match by reference
    UI->>Store: auto_match_by_reference(...)
    Store->>DB: Update bank_transactions.donation_id

    Finance->>UI: Manual match exceptions
    UI->>Store: match_donation_to_bank_transaction(...)
    Store->>DB: Persist final matches
```

### HIPAA-sensitive data review

```mermaid
sequenceDiagram
    actor Compliance
    participant UI as HIPAA Review Tab
    participant Store as CRMStore
    participant Scanner as HipaaSensitivityScanner
    participant DB as SQLite

    Compliance->>UI: Run AI Scan
    UI->>Store: records_for_hipaa_scan()
    Store->>DB: Read CRM objects
    Store-->>UI: Normalized record payloads
    UI->>Scanner: scan_records(records)
    Scanner-->>UI: Ranked findings with severity/confidence
    UI->>UI: Filter, review, export CSV
```

## Module responsibilities

- `nonprofit_crm_app.py`: CRM user interface, tab workflows, and report rendering.
- `nonprofit_crm/store.py`: schema management, data access, reconciliation logic, and operational calculations.
- `nonprofit_crm/hipaa_scan.py`: heuristic AI-assisted sensitive-data detection and finding scoring.
- `nonprofit_crm/__init__.py`: package exports for app and tests.

## Data model overview

Primary tables managed by `CRMStore`:

- `donors`: accounts/contacts and relationship owner metadata.
- `engagements`: stewardship activity history and follow-up tasks.
- `donations`: opportunity/gift records, stage, probability, fund/campaign fields.
- `campaigns`: fundraising initiatives, hierarchy, and rollup attribution.
- `ledger_entries`: accounting-side posting records.
- `bank_accounts`: financial account catalog.
- `bank_transactions`: imported/entered bank movement used for reconciliation.

## Runtime state

The app keeps lightweight UI state in `st.session_state`, including:

- search panel state,
- HIPAA scan results and scan timestamp,
- form selections and filter values.

Source-of-truth business data remains in SQLite.

## Known limitations

- Authentication and role-based access control are not yet built in.
- SQLite is suitable for local/small-team usage; production should use managed relational infrastructure.
- HIPAA review findings are heuristic and require human compliance review.

## Extension points

- Add SSO, RBAC, and immutable audit trails.
- Move persistence to PostgreSQL or another managed database.
- Add background jobs for imports and monthly reconciliation automation.
- Expand HIPAA scanner rules and include policy-driven custom detectors.
