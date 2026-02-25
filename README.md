# Nonprofit CRM

[![CI](https://github.com/huskerwin/nonprofitcrm/actions/workflows/ci.yml/badge.svg)](https://github.com/huskerwin/nonprofitcrm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

This repository contains a Streamlit-based nonprofit CRM focused on donor relationship management, fundraising operations, accounting traceability, and compliance review.

## Core capabilities

- Salesforce Nonprofit Cloud-inspired workspace and object model
- Accounts and Contacts for individual and organization records
- Engagement Plans with activity history and follow-up tasks
- Opportunities with stage, probability, campaign, and funding metadata
- Campaign hierarchy and campaign performance rollups
- Gift Entry and Ledger linking for audit-ready financial traceability
- Bank transaction management and month-end reconciliation workflow
- AI-assisted HIPAA-sensitive data review across CRM records

## Quick start

1. Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the CRM app:

```bash
streamlit run nonprofit_crm_app.py
```

The app uses SQLite by default and stores data in `.data/nonprofit_crm.db`.

## Documentation

- System architecture: `docs/architecture.md`
- Operations and workflow guide: `docs/usage.md`
- Deployment and production guidance: `docs/deployment.md`
- Release history: `CHANGELOG.md`

## Running tests

```bash
python -m pytest -q
```

## Project standards

- License: `LICENSE` (MIT)
- Contributing: `CONTRIBUTING.md`
- Code of conduct: `CODE_OF_CONDUCT.md`
- Security policy: `SECURITY.md`
- Support channels: `SUPPORT.md`
