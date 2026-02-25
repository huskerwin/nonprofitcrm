# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog:
https://keepachangelog.com/en/1.1.0/

## [Unreleased]

### Added

- AI-assisted HIPAA-sensitive data review tab with filterable findings and CSV export
- Heuristic HIPAA scanner module for SSN, DOB, MRN, insurance, coding, and medical-context signals
- Smart account/contact search improvements with alias and fuzzy name matching

### Changed

- Updated repository documentation to be fully nonprofit CRM focused
- Expanded CRM architecture and usage guidance for fundraising and finance workflows

## [1.0.0] - 2026-02-24

### Added

- Salesforce Nonprofit Cloud-inspired CRM workspace built with Streamlit
- Accounts/Contacts, Engagement Plans, Opportunities, Campaigns, and Gift Entry modules
- Reconciliation flow linking opportunities, ledger entries, and bank transactions
- SQLite-backed persistence layer with schema initialization and migrations
- Unit test suite for CRM store behavior and reconciliation correctness
