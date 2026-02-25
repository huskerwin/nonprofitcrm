# Usage Guide

This guide explains how to run and operate the nonprofit CRM.

## Prerequisites

- Python 3.11+
- Access to the repository and local write permissions for `.data/`

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run the CRM

```bash
streamlit run nonprofit_crm_app.py
```

By default, data is stored in `.data/nonprofit_crm.db`.

## Main navigation

- `Home`: KPIs, pipeline view, follow-ups, and finance exceptions.
- `Accounts & Contacts`: constituent records and relationship history.
- `Engagement Plans`: activities, stewardship tasks, and due dates.
- `Opportunities`: gift pipeline, stage updates, and opportunity register.
- `Campaigns`: campaign hierarchy, progress, and influence rollups.
- `Gift Entry & Ledger`: accounting-side entries and gift linkage.
- `Reconciliation`: bank matching, variance tracking, and monthly close.
- `HIPAA Review`: AI-assisted sensitive-data scan and review export.

## Typical operating workflow

1. Add records in `Accounts & Contacts`.
2. Log interactions in `Engagement Plans`.
3. Create and progress gifts in `Opportunities`.
4. Associate gifts to initiatives in `Campaigns`.
5. Record accounting entries in `Gift Entry & Ledger`.
6. Import or add bank activity and reconcile in `Reconciliation`.
7. Run `HIPAA Review` for compliance screening and export findings.

## HIPAA review workflow

1. Open `HIPAA Review`.
2. Click **Run AI Scan**.
3. Review findings by severity, object, and keyword filters.
4. Export findings with **Download Findings CSV** for compliance follow-up.

## Troubleshooting

### App starts but no data appears

- Confirm records were created in the relevant object tab.
- Verify `.data/nonprofit_crm.db` is writable.
- Re-run the app after schema updates.

### Reconciliation numbers do not match

- Ensure opportunity amounts exactly match bank transaction amounts.
- Check for missing ledger links.
- Use auto-match by reference before manual matching.

### HIPAA scan has no results when expected

- Confirm sensitive details exist in text fields (notes/summary/description).
- Re-run the scan after any data edits.
- Review scanner limitations in `docs/architecture.md`.
