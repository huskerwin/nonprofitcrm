# Deployment Notes

This CRM is optimized for local and small-team use by default. For production, plan for identity controls, managed persistence, auditability, and resilience.

## Recommended production baseline

- Place the app behind authenticated access (SSO/OIDC + MFA).
- Replace local SQLite with managed relational storage (for example, PostgreSQL).
- Centralize logs, metrics, and alerting for operational monitoring.
- Encrypt data in transit and at rest.
- Run scheduled backups with restore validation.

## Infrastructure pattern

- App tier: Streamlit service hosting `nonprofit_crm_app.py`.
- Data tier: managed relational database for CRM objects and reconciliation records.
- Secrets tier: environment-injected secrets from a secret manager.
- Operations tier: log aggregation, health checks, and uptime monitoring.

## Containerization

When containerizing, include:

- Python runtime matching `requirements.txt`
- application code for `nonprofit_crm_app.py` and `nonprofit_crm/`
- read/write storage mount for runtime data (if local file storage is still used)

## Security and compliance controls

- Do not commit secrets or credentials.
- Enforce least-privilege access to CRM data and infrastructure.
- Add role-based access controls for fundraising, finance, and admin personas.
- Maintain immutable audit logs for sensitive updates and exports.
- Define retention and deletion policies aligned with compliance needs.

## HIPAA-oriented hardening checklist

- Signed BAAs with in-scope vendors.
- Strong authentication and session controls.
- Access logging and anomaly detection.
- Incident response and breach reporting procedures.
- Formal risk assessments and remediation tracking.

## Scaling considerations

- Move heavy imports and reconciliation tasks to asynchronous workers.
- Use connection pooling for high-concurrency workloads.
- Add background jobs for scheduled scans and monthly close automation.
