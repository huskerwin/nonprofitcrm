"""SQLite-backed persistence layer for a nonprofit CRM."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_token(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _normalize_digits(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\D", "", value)


def _build_alias_lookup() -> dict[str, set[str]]:
    groups = (
        ("alexander", "alex", "xander", "sasha"),
        ("andrew", "andy", "drew"),
        ("anthony", "tony"),
        ("benjamin", "ben", "benny"),
        ("charles", "charlie", "chuck"),
        ("christopher", "chris"),
        ("daniel", "dan", "danny"),
        ("david", "dave", "davy"),
        ("elizabeth", "liz", "beth", "lizzy", "eliza"),
        ("james", "jim", "jimmy"),
        ("jennifer", "jen", "jenny"),
        ("joseph", "joe", "joey"),
        ("katherine", "kathryn", "kate", "katie", "kat"),
        ("margaret", "maggie", "meg", "peggy"),
        ("matthew", "matt"),
        ("michael", "mike", "mikey"),
        ("nicholas", "nick", "nicky", "nik"),
        ("patrick", "pat", "paddy"),
        ("robert", "rob", "bob", "bobby"),
        ("samantha", "sam", "sammy"),
        ("stephanie", "steph"),
        ("stephen", "steve", "steven"),
        ("thomas", "tom", "tommy"),
        ("victoria", "vicky", "tori"),
        ("william", "will", "bill", "billy", "liam"),
    )

    lookup: dict[str, set[str]] = {}
    for group in groups:
        normalized_group = {token for token in (_normalize_token(name) for name in group) if token}
        for token in normalized_group:
            existing = lookup.setdefault(token, set())
            existing.update(normalized_group)
    return lookup


_ALIAS_LOOKUP = _build_alias_lookup()


def _name_aliases(value: str | None) -> set[str]:
    token = _normalize_token(value)
    if not token:
        return set()

    aliases = {token}
    aliases.update(_ALIAS_LOOKUP.get(token, set()))
    return aliases


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _donor_search_score(row: sqlite3.Row, search_term: str) -> float:
    query_norm = _normalize_token(search_term)
    if not query_norm:
        return 0.0

    query_digits = _normalize_digits(search_term)
    search_tokens = [token for token in search_term.strip().split() if token]

    first_name = row["first_name"] or ""
    last_name = row["last_name"] or ""
    organization_name = row["organization_name"] or ""
    email = row["email"] or ""
    phone = row["phone"] or ""

    full_name = f"{first_name} {last_name}".strip()

    first_norm = _normalize_token(first_name)
    last_norm = _normalize_token(last_name)
    full_norm = _normalize_token(full_name)
    org_norm = _normalize_token(organization_name)
    email_norm = _normalize_token(email)
    phone_digits = _normalize_digits(phone)

    searchable_text = [full_norm, first_norm, last_norm, org_norm, email_norm]

    score = 0.0

    if any(query_norm == field for field in searchable_text if field):
        score += 240
    elif any(query_norm in field for field in searchable_text if field):
        score += 150

    if query_digits and phone_digits:
        if query_digits == phone_digits:
            score += 240
        elif query_digits in phone_digits:
            score += 150

    for token in search_tokens:
        token_aliases = _name_aliases(token)
        if first_norm and first_norm in token_aliases:
            score += 130
        if last_norm and last_norm in token_aliases:
            score += 90

    best_ratio = max(
        _similarity(query_norm, first_norm),
        _similarity(query_norm, last_norm),
        _similarity(query_norm, full_norm),
        _similarity(query_norm, org_norm),
        _similarity(query_norm, email_norm),
    )

    if best_ratio >= 0.9:
        score += 120
    elif best_ratio >= 0.8:
        score += 80
    elif best_ratio >= 0.7:
        score += 45
    elif best_ratio >= 0.62:
        score += 20

    if first_norm.startswith(query_norm) or last_norm.startswith(query_norm):
        score += 70

    if len(query_norm) >= 4 and (query_norm in first_norm or query_norm in last_norm):
        score += 40

    return score


def _lastrowid(cursor: sqlite3.Cursor) -> int:
    row_id = cursor.lastrowid
    if row_id is None:
        raise RuntimeError("Insert did not return a row id.")
    return row_id


def cents_from_amount(amount: float) -> int:
    return int(round(amount * 100))


def amount_from_cents(cents: int) -> float:
    return cents / 100


def format_currency(cents: int) -> str:
    return f"${amount_from_cents(cents):,.2f}"


def donor_display_name(row: sqlite3.Row | dict[str, Any]) -> str:
    donor_type = row["donor_type"]
    if donor_type == "Organization":
        organization_name = row["organization_name"]
        return organization_name or "Unnamed organization"

    first_name = (row["first_name"] or "").strip()
    last_name = (row["last_name"] or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    return full_name or "Unnamed donor"


@dataclass(frozen=True)
class MonthRange:
    start: date
    end: date


def month_bounds(anchor: date) -> MonthRange:
    first_day = anchor.replace(day=1)
    if first_day.month == 12:
        next_month = date(first_day.year + 1, 1, 1)
    else:
        next_month = date(first_day.year, first_day.month + 1, 1)
    return MonthRange(start=first_day, end=next_month - timedelta(days=1))


def _month_shift(first_day_of_month: date, months_back: int) -> date:
    year = first_day_of_month.year
    month = first_day_of_month.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    if column_name in _table_columns(connection, table_name):
        return
    connection.execute(
        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
    )


class CRMStore:
    """Persistence operations for donors, gifts, engagements, and reconciliation."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS donors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    donor_type TEXT NOT NULL CHECK (donor_type IN ('Individual', 'Organization')),
                    first_name TEXT,
                    last_name TEXT,
                    organization_name TEXT,
                    email TEXT,
                    phone TEXT,
                    lifecycle_stage TEXT NOT NULL DEFAULT 'Prospect',
                    relationship_manager TEXT,
                    preferred_channel TEXT,
                    notes TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS engagements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    donor_id INTEGER NOT NULL,
                    engagement_date TEXT NOT NULL,
                    engagement_type TEXT NOT NULL,
                    channel TEXT,
                    summary TEXT NOT NULL,
                    next_step TEXT,
                    follow_up_date TEXT,
                    owner TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (donor_id) REFERENCES donors(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS bank_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    bank_name TEXT,
                    account_last4 TEXT,
                    currency TEXT NOT NULL DEFAULT 'USD',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS ledger_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    posted_date TEXT NOT NULL,
                    account_code TEXT NOT NULL,
                    description TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL,
                    reference_code TEXT,
                    source TEXT NOT NULL DEFAULT 'Manual',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    campaign_type TEXT NOT NULL DEFAULT 'Fundraising',
                    status TEXT NOT NULL DEFAULT 'Planned',
                    owner TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    goal_cents INTEGER NOT NULL DEFAULT 0,
                    parent_campaign_id INTEGER,
                    description TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parent_campaign_id) REFERENCES campaigns(id)
                );

                CREATE TABLE IF NOT EXISTS donations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    donor_id INTEGER NOT NULL,
                    donation_date TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                    donation_type TEXT NOT NULL DEFAULT 'One-time',
                    campaign TEXT,
                    fund TEXT,
                    payment_method TEXT,
                    reference_code TEXT,
                    bank_account_id INTEGER,
                    ledger_entry_id INTEGER,
                    is_anonymous INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (donor_id) REFERENCES donors(id) ON DELETE CASCADE,
                    FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id),
                    FOREIGN KEY (ledger_entry_id) REFERENCES ledger_entries(id)
                );

                CREATE TABLE IF NOT EXISTS bank_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bank_account_id INTEGER NOT NULL,
                    transaction_date TEXT NOT NULL,
                    description TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL,
                    reference_code TEXT,
                    donation_id INTEGER,
                    ledger_entry_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id),
                    FOREIGN KEY (donation_id) REFERENCES donations(id),
                    FOREIGN KEY (ledger_entry_id) REFERENCES ledger_entries(id)
                );

                CREATE INDEX IF NOT EXISTS idx_donations_date ON donations (donation_date);
                CREATE INDEX IF NOT EXISTS idx_donations_donor ON donations (donor_id);
                CREATE INDEX IF NOT EXISTS idx_engagements_donor ON engagements (donor_id);
                CREATE INDEX IF NOT EXISTS idx_engagements_follow_up ON engagements (follow_up_date);
                CREATE INDEX IF NOT EXISTS idx_campaigns_name ON campaigns (name);
                CREATE INDEX IF NOT EXISTS idx_campaigns_parent ON campaigns (parent_campaign_id);
                CREATE INDEX IF NOT EXISTS idx_bank_transactions_date ON bank_transactions (transaction_date);
                CREATE INDEX IF NOT EXISTS idx_bank_transactions_donation ON bank_transactions (donation_id);
                """
            )

            _ensure_column(
                connection=connection,
                table_name="donations",
                column_name="opportunity_name",
                definition="TEXT",
            )
            _ensure_column(
                connection=connection,
                table_name="donations",
                column_name="opportunity_stage",
                definition="TEXT NOT NULL DEFAULT 'Closed Won'",
            )
            _ensure_column(
                connection=connection,
                table_name="donations",
                column_name="close_date",
                definition="TEXT",
            )
            _ensure_column(
                connection=connection,
                table_name="donations",
                column_name="campaign_id",
                definition="INTEGER",
            )
            _ensure_column(
                connection=connection,
                table_name="donations",
                column_name="probability_percent",
                definition="INTEGER NOT NULL DEFAULT 100",
            )

            donation_column_names = _table_columns(connection, "donations")
            if "opportunity_name" in donation_column_names:
                connection.execute(
                    """
                    UPDATE donations
                    SET opportunity_name = COALESCE(opportunity_name, 'Donation #' || id)
                    WHERE opportunity_name IS NULL OR TRIM(opportunity_name) = ''
                    """
                )
            if "close_date" in donation_column_names:
                connection.execute(
                    """
                    UPDATE donations
                    SET close_date = COALESCE(close_date, donation_date)
                    WHERE close_date IS NULL OR TRIM(close_date) = ''
                    """
                )

            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_donations_stage ON donations (opportunity_stage)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_donations_campaign_id ON donations (campaign_id)"
            )

            count_row = connection.execute(
                "SELECT COUNT(*) AS count FROM bank_accounts"
            ).fetchone()
            if count_row and count_row["count"] == 0:
                connection.execute(
                    """
                    INSERT INTO bank_accounts (name, bank_name, account_last4)
                    VALUES (?, ?, ?)
                    """,
                    ("Operating Account", "Primary Bank", "0000"),
                )

    def add_donor(
        self,
        donor_type: str,
        first_name: str | None,
        last_name: str | None,
        organization_name: str | None,
        email: str | None,
        phone: str | None,
        lifecycle_stage: str,
        relationship_manager: str | None,
        preferred_channel: str | None,
        notes: str | None,
    ) -> int:
        clean_first = _clean(first_name)
        clean_last = _clean(last_name)
        clean_org = _clean(organization_name)

        if donor_type == "Individual":
            if not clean_first or not clean_last:
                raise ValueError("Individual donors require first and last name.")
            clean_org = None
        elif donor_type == "Organization":
            if not clean_org:
                raise ValueError("Organization donors require an organization name.")
            clean_first = None
            clean_last = None
        else:
            raise ValueError("Donor type must be Individual or Organization.")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO donors (
                    donor_type,
                    first_name,
                    last_name,
                    organization_name,
                    email,
                    phone,
                    lifecycle_stage,
                    relationship_manager,
                    preferred_channel,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    donor_type,
                    clean_first,
                    clean_last,
                    clean_org,
                    _clean(email),
                    _clean(phone),
                    lifecycle_stage,
                    _clean(relationship_manager),
                    _clean(preferred_channel),
                    _clean(notes),
                ),
            )
            return _lastrowid(cursor)

    def get_donor(self, donor_id: int) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM donors WHERE id = ?",
                (donor_id,),
            ).fetchone()

    def list_donors(
        self,
        search_term: str = "",
        smart_search: bool = False,
    ) -> list[sqlite3.Row]:
        cleaned_search = search_term.strip()

        base_select = """
            SELECT
                d.*,
                (
                    SELECT COALESCE(SUM(amount_cents), 0)
                    FROM donations dn
                    WHERE dn.donor_id = d.id
                ) AS total_given_cents,
                (
                    SELECT MAX(donation_date)
                    FROM donations dn
                    WHERE dn.donor_id = d.id
                ) AS last_donation_date,
                (
                    SELECT COUNT(*)
                    FROM engagements e
                    WHERE e.donor_id = d.id
                ) AS engagement_count
            FROM donors d
        """

        order_sql = " ORDER BY d.created_at DESC, d.id DESC"

        with self._connect() as connection:
            if not cleaned_search:
                query = f"{base_select}{order_sql}"
                return connection.execute(query).fetchall()

            if not smart_search:
                where_sql = """
                    WHERE (
                        COALESCE(first_name, '') LIKE ? OR
                        COALESCE(last_name, '') LIKE ? OR
                        COALESCE(organization_name, '') LIKE ? OR
                        COALESCE(email, '') LIKE ? OR
                        COALESCE(phone, '') LIKE ?
                    )
                """
                wildcard = f"%{cleaned_search}%"
                query = f"{base_select}{where_sql}{order_sql}"
                return connection.execute(
                    query,
                    [wildcard, wildcard, wildcard, wildcard, wildcard],
                ).fetchall()

            broad_query = f"{base_select}{order_sql}"
            candidates = connection.execute(broad_query).fetchall()

        scored_candidates: list[tuple[float, sqlite3.Row]] = []
        for row in candidates:
            score = _donor_search_score(row, cleaned_search)
            if score >= 55:
                scored_candidates.append((score, row))

        scored_candidates.sort(
            key=lambda scored: (
                scored[0],
                scored[1]["last_donation_date"] or "",
                scored[1]["created_at"],
                scored[1]["id"],
            ),
            reverse=True,
        )

        return [row for _, row in scored_candidates]

    def records_for_hipaa_scan(self) -> list[dict[str, Any]]:
        """Return CRM records prepared for sensitive-data scanning."""

        object_tables = [
            ("Accounts & Contacts", "donors"),
            ("Engagement Plans", "engagements"),
            ("Opportunities", "donations"),
            ("Campaigns", "campaigns"),
            ("Gift Entry & Ledger", "ledger_entries"),
            ("Bank Accounts", "bank_accounts"),
            ("Bank Transactions", "bank_transactions"),
        ]

        records: list[dict[str, Any]] = []
        with self._connect() as connection:
            for object_name, table_name in object_tables:
                rows = connection.execute(
                    f"SELECT * FROM {table_name} ORDER BY id DESC"
                ).fetchall()

                for row in rows:
                    row_dict = dict(row)
                    record_id = row_dict.get("id")
                    if not isinstance(record_id, int):
                        continue

                    fields: dict[str, Any] = {}
                    for key, value in row_dict.items():
                        if key in {"id", "created_at"}:
                            continue
                        if value is None:
                            continue
                        if isinstance(value, str):
                            cleaned = value.strip()
                            if not cleaned:
                                continue
                            fields[key] = cleaned
                            continue
                        if isinstance(value, (int, float)):
                            continue
                        fields[key] = str(value)

                    records.append(
                        {
                            "object_name": object_name,
                            "table_name": table_name,
                            "record_id": record_id,
                            "fields": fields,
                        }
                    )

        return records

    def add_campaign(
        self,
        name: str,
        campaign_type: str,
        status: str,
        owner: str | None,
        start_date: date | None,
        end_date: date | None,
        goal_cents: int,
        parent_campaign_id: int | None,
        description: str | None,
    ) -> int:
        clean_name = _clean(name)
        if not clean_name:
            raise ValueError("Campaign name is required.")
        if goal_cents < 0:
            raise ValueError("Campaign goal cannot be negative.")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO campaigns (
                    name,
                    campaign_type,
                    status,
                    owner,
                    start_date,
                    end_date,
                    goal_cents,
                    parent_campaign_id,
                    description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_name,
                    _clean(campaign_type) or "Fundraising",
                    _clean(status) or "Planned",
                    _clean(owner),
                    start_date.isoformat() if start_date else None,
                    end_date.isoformat() if end_date else None,
                    goal_cents,
                    parent_campaign_id,
                    _clean(description),
                ),
            )
            return _lastrowid(cursor)

    def list_campaigns(self, active_only: bool = True) -> list[sqlite3.Row]:
        where_sql = "WHERE c.active = 1" if active_only else ""
        query = f"""
            SELECT
                c.*,
                parent.name AS parent_campaign_name,
                COUNT(dn.id) AS gift_count,
                COALESCE(SUM(dn.amount_cents), 0) AS raised_cents
            FROM campaigns c
            LEFT JOIN campaigns parent ON parent.id = c.parent_campaign_id
            LEFT JOIN donations dn ON dn.campaign_id = c.id
            {where_sql}
            GROUP BY c.id
            ORDER BY c.created_at DESC, c.id DESC
        """
        with self._connect() as connection:
            return connection.execute(query).fetchall()

    def opportunity_pipeline(self) -> list[sqlite3.Row]:
        query = """
            SELECT
                COALESCE(opportunity_stage, 'Closed Won') AS stage_name,
                COUNT(*) AS opportunity_count,
                COALESCE(SUM(amount_cents), 0) AS total_cents
            FROM donations
            GROUP BY COALESCE(opportunity_stage, 'Closed Won')
            ORDER BY
                CASE COALESCE(opportunity_stage, 'Closed Won')
                    WHEN 'Prospecting' THEN 1
                    WHEN 'Cultivation' THEN 2
                    WHEN 'Pledged' THEN 3
                    WHEN 'Closed Won' THEN 4
                    WHEN 'Closed Lost' THEN 5
                    ELSE 99
                END,
                stage_name
        """
        with self._connect() as connection:
            return connection.execute(query).fetchall()

    def update_opportunity_stage(
        self,
        donation_id: int,
        stage_name: str,
        probability_percent: int | None = None,
    ) -> None:
        clean_stage = _clean(stage_name)
        if not clean_stage:
            raise ValueError("Opportunity stage is required.")

        with self._connect() as connection:
            if probability_percent is None:
                connection.execute(
                    """
                    UPDATE donations
                    SET opportunity_stage = ?
                    WHERE id = ?
                    """,
                    (clean_stage, donation_id),
                )
                return

            bounded_probability = max(0, min(probability_percent, 100))
            connection.execute(
                """
                UPDATE donations
                SET opportunity_stage = ?, probability_percent = ?
                WHERE id = ?
                """,
                (clean_stage, bounded_probability, donation_id),
            )

    def add_engagement(
        self,
        donor_id: int,
        engagement_date: date,
        engagement_type: str,
        channel: str | None,
        summary: str,
        next_step: str | None,
        follow_up_date: date | None,
        owner: str | None,
    ) -> int:
        if not _clean(summary):
            raise ValueError("Engagement summary is required.")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO engagements (
                    donor_id,
                    engagement_date,
                    engagement_type,
                    channel,
                    summary,
                    next_step,
                    follow_up_date,
                    owner
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    donor_id,
                    engagement_date.isoformat(),
                    engagement_type,
                    _clean(channel),
                    summary.strip(),
                    _clean(next_step),
                    follow_up_date.isoformat() if follow_up_date else None,
                    _clean(owner),
                ),
            )
            return _lastrowid(cursor)

    def list_engagements(
        self,
        donor_id: int | None = None,
        limit: int = 200,
    ) -> list[sqlite3.Row]:
        where_clauses: list[str] = []
        parameters: list[Any] = []

        if donor_id is not None:
            where_clauses.append("e.donor_id = ?")
            parameters.append(donor_id)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"""
            SELECT
                e.*,
                d.donor_type,
                d.first_name,
                d.last_name,
                d.organization_name
            FROM engagements e
            JOIN donors d ON d.id = e.donor_id
            {where_sql}
            ORDER BY e.engagement_date DESC, e.id DESC
            LIMIT ?
        """
        parameters.append(limit)

        with self._connect() as connection:
            return connection.execute(query, parameters).fetchall()

    def add_bank_account(
        self,
        name: str,
        bank_name: str | None,
        account_last4: str | None,
        currency: str = "USD",
    ) -> int:
        clean_name = _clean(name)
        if not clean_name:
            raise ValueError("Bank account name is required.")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO bank_accounts (name, bank_name, account_last4, currency)
                VALUES (?, ?, ?, ?)
                """,
                (
                    clean_name,
                    _clean(bank_name),
                    _clean(account_last4),
                    (currency or "USD").strip().upper(),
                ),
            )
            return _lastrowid(cursor)

    def list_bank_accounts(self, active_only: bool = True) -> list[sqlite3.Row]:
        query = "SELECT * FROM bank_accounts"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY name ASC, id ASC"

        with self._connect() as connection:
            return connection.execute(query).fetchall()

    def add_ledger_entry(
        self,
        posted_date: date,
        account_code: str,
        description: str,
        amount_cents: int,
        reference_code: str | None,
        source: str = "Manual",
    ) -> int:
        clean_account_code = _clean(account_code)
        clean_description = _clean(description)
        if not clean_account_code:
            raise ValueError("Account code is required.")
        if not clean_description:
            raise ValueError("Ledger description is required.")
        if amount_cents == 0:
            raise ValueError("Ledger amount cannot be zero.")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO ledger_entries (
                    posted_date,
                    account_code,
                    description,
                    amount_cents,
                    reference_code,
                    source
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    posted_date.isoformat(),
                    clean_account_code,
                    clean_description,
                    amount_cents,
                    _clean(reference_code),
                    _clean(source) or "Manual",
                ),
            )
            return _lastrowid(cursor)

    def list_ledger_entries(
        self,
        unlinked_only: bool = False,
        month_start: date | None = None,
        month_end: date | None = None,
    ) -> list[sqlite3.Row]:
        where_clauses: list[str] = []
        parameters: list[Any] = []

        if month_start is not None:
            where_clauses.append("le.posted_date >= ?")
            parameters.append(month_start.isoformat())
        if month_end is not None:
            where_clauses.append("le.posted_date <= ?")
            parameters.append(month_end.isoformat())

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"""
            SELECT
                le.*,
                COUNT(dn.id) AS linked_donations
            FROM ledger_entries le
            LEFT JOIN donations dn ON dn.ledger_entry_id = le.id
            {where_sql}
            GROUP BY le.id
        """

        if unlinked_only:
            query += " HAVING COUNT(dn.id) = 0"

        query += " ORDER BY le.posted_date DESC, le.id DESC"

        with self._connect() as connection:
            return connection.execute(query, parameters).fetchall()

    def add_donation(
        self,
        donor_id: int,
        donation_date: date,
        amount_cents: int,
        donation_type: str,
        campaign: str | None,
        fund: str | None,
        payment_method: str | None,
        reference_code: str | None,
        bank_account_id: int | None,
        ledger_entry_id: int | None,
        notes: str | None,
        is_anonymous: bool = False,
        opportunity_name: str | None = None,
        opportunity_stage: str = "Closed Won",
        close_date: date | None = None,
        campaign_id: int | None = None,
        probability_percent: int = 100,
    ) -> int:
        if amount_cents <= 0:
            raise ValueError("Donation amount must be greater than zero.")

        clean_opportunity_name = _clean(opportunity_name)
        if clean_opportunity_name is None:
            clean_opportunity_name = f"Donation on {donation_date.isoformat()}"

        clean_stage = _clean(opportunity_stage) or "Closed Won"
        bounded_probability = max(0, min(probability_percent, 100))

        inferred_campaign = _clean(campaign)
        if campaign_id is not None and inferred_campaign is None:
            with self._connect() as connection:
                campaign_row = connection.execute(
                    "SELECT name FROM campaigns WHERE id = ?",
                    (campaign_id,),
                ).fetchone()
                if campaign_row is not None:
                    inferred_campaign = campaign_row["name"]

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO donations (
                    donor_id,
                    donation_date,
                    amount_cents,
                    donation_type,
                    campaign,
                    fund,
                    payment_method,
                    reference_code,
                    bank_account_id,
                    ledger_entry_id,
                    notes,
                    is_anonymous,
                    opportunity_name,
                    opportunity_stage,
                    close_date,
                    campaign_id,
                    probability_percent
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    donor_id,
                    donation_date.isoformat(),
                    amount_cents,
                    donation_type,
                    inferred_campaign,
                    _clean(fund),
                    _clean(payment_method),
                    _clean(reference_code),
                    bank_account_id,
                    ledger_entry_id,
                    _clean(notes),
                    1 if is_anonymous else 0,
                    clean_opportunity_name,
                    clean_stage,
                    (close_date or donation_date).isoformat(),
                    campaign_id,
                    bounded_probability,
                ),
            )
            return _lastrowid(cursor)

    def list_donations(
        self,
        donor_id: int | None = None,
        bank_account_id: int | None = None,
        month_start: date | None = None,
        month_end: date | None = None,
        unreconciled_only: bool = False,
        opportunity_stage: str | None = None,
        campaign_id: int | None = None,
        open_only: bool = False,
    ) -> list[sqlite3.Row]:
        where_clauses: list[str] = []
        parameters: list[Any] = []

        if donor_id is not None:
            where_clauses.append("dn.donor_id = ?")
            parameters.append(donor_id)
        if bank_account_id is not None:
            where_clauses.append("dn.bank_account_id = ?")
            parameters.append(bank_account_id)
        if month_start is not None:
            where_clauses.append("dn.donation_date >= ?")
            parameters.append(month_start.isoformat())
        if month_end is not None:
            where_clauses.append("dn.donation_date <= ?")
            parameters.append(month_end.isoformat())
        if opportunity_stage is not None:
            where_clauses.append("COALESCE(dn.opportunity_stage, 'Closed Won') = ?")
            parameters.append(opportunity_stage)
        if campaign_id is not None:
            where_clauses.append("dn.campaign_id = ?")
            parameters.append(campaign_id)
        if open_only:
            where_clauses.append(
                "COALESCE(dn.opportunity_stage, 'Closed Won') NOT IN ('Closed Won', 'Closed Lost')"
            )
        if unreconciled_only:
            where_clauses.append(
                """
                (
                    dn.ledger_entry_id IS NULL OR
                    NOT EXISTS (
                        SELECT 1
                        FROM bank_transactions bt
                        WHERE bt.donation_id = dn.id
                    )
                )
                """
            )

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"""
            SELECT
                dn.*,
                d.donor_type,
                d.first_name,
                d.last_name,
                d.organization_name,
                ba.name AS bank_account_name,
                cp.name AS campaign_name,
                COALESCE(cp.name, dn.campaign) AS campaign_label,
                CASE WHEN dn.ledger_entry_id IS NULL THEN 0 ELSE 1 END AS has_ledger_link,
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM bank_transactions bt
                        WHERE bt.donation_id = dn.id
                    ) THEN 1
                    ELSE 0
                END AS has_bank_match
            FROM donations dn
            JOIN donors d ON d.id = dn.donor_id
            LEFT JOIN bank_accounts ba ON ba.id = dn.bank_account_id
            LEFT JOIN campaigns cp ON cp.id = dn.campaign_id
            {where_sql}
            ORDER BY COALESCE(dn.close_date, dn.donation_date) DESC, dn.id DESC
        """

        with self._connect() as connection:
            return connection.execute(query, parameters).fetchall()

    def add_bank_transaction(
        self,
        bank_account_id: int,
        transaction_date: date,
        description: str,
        amount_cents: int,
        reference_code: str | None,
    ) -> int:
        clean_description = _clean(description)
        if not clean_description:
            raise ValueError("Bank transaction description is required.")
        if amount_cents == 0:
            raise ValueError("Bank transaction amount cannot be zero.")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO bank_transactions (
                    bank_account_id,
                    transaction_date,
                    description,
                    amount_cents,
                    reference_code
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    bank_account_id,
                    transaction_date.isoformat(),
                    clean_description,
                    amount_cents,
                    _clean(reference_code),
                ),
            )
            return _lastrowid(cursor)

    def list_bank_transactions(
        self,
        bank_account_id: int | None = None,
        month_start: date | None = None,
        month_end: date | None = None,
        unmatched_only: bool = False,
    ) -> list[sqlite3.Row]:
        where_clauses: list[str] = []
        parameters: list[Any] = []

        if bank_account_id is not None:
            where_clauses.append("bt.bank_account_id = ?")
            parameters.append(bank_account_id)
        if month_start is not None:
            where_clauses.append("bt.transaction_date >= ?")
            parameters.append(month_start.isoformat())
        if month_end is not None:
            where_clauses.append("bt.transaction_date <= ?")
            parameters.append(month_end.isoformat())
        if unmatched_only:
            where_clauses.append("bt.donation_id IS NULL")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"""
            SELECT
                bt.*,
                ba.name AS bank_account_name,
                dn.amount_cents AS donation_amount_cents,
                d.donor_type,
                d.first_name,
                d.last_name,
                d.organization_name
            FROM bank_transactions bt
            LEFT JOIN bank_accounts ba ON ba.id = bt.bank_account_id
            LEFT JOIN donations dn ON dn.id = bt.donation_id
            LEFT JOIN donors d ON d.id = dn.donor_id
            {where_sql}
            ORDER BY bt.transaction_date DESC, bt.id DESC
        """

        with self._connect() as connection:
            return connection.execute(query, parameters).fetchall()

    def link_donation_to_ledger(self, donation_id: int, ledger_entry_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE donations SET ledger_entry_id = ? WHERE id = ?",
                (ledger_entry_id, donation_id),
            )

    def link_bank_transaction_to_ledger(self, bank_transaction_id: int, ledger_entry_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE bank_transactions SET ledger_entry_id = ? WHERE id = ?",
                (ledger_entry_id, bank_transaction_id),
            )

    def match_donation_to_bank_transaction(
        self,
        donation_id: int,
        bank_transaction_id: int,
    ) -> None:
        with self._connect() as connection:
            donation = connection.execute(
                "SELECT id, amount_cents, bank_account_id, ledger_entry_id FROM donations WHERE id = ?",
                (donation_id,),
            ).fetchone()
            bank_transaction = connection.execute(
                """
                SELECT id, amount_cents, bank_account_id, donation_id, ledger_entry_id
                FROM bank_transactions
                WHERE id = ?
                """,
                (bank_transaction_id,),
            ).fetchone()

            if donation is None:
                raise ValueError("Donation record was not found.")
            if bank_transaction is None:
                raise ValueError("Bank transaction record was not found.")
            if bank_transaction["donation_id"] is not None:
                raise ValueError("Bank transaction is already matched to another donation.")

            if donation["amount_cents"] != bank_transaction["amount_cents"]:
                raise ValueError("Amounts do not match. Reconciliation requires exact value match.")

            donor_bank_account = donation["bank_account_id"]
            transaction_bank_account = bank_transaction["bank_account_id"]
            if donor_bank_account is not None and donor_bank_account != transaction_bank_account:
                raise ValueError("Bank account mismatch between donation and bank transaction.")

            connection.execute(
                "UPDATE bank_transactions SET donation_id = ? WHERE id = ?",
                (donation_id, bank_transaction_id),
            )

            if donor_bank_account is None:
                connection.execute(
                    "UPDATE donations SET bank_account_id = ? WHERE id = ?",
                    (transaction_bank_account, donation_id),
                )

            if (
                donation["ledger_entry_id"] is not None
                and bank_transaction["ledger_entry_id"] is None
            ):
                connection.execute(
                    "UPDATE bank_transactions SET ledger_entry_id = ? WHERE id = ?",
                    (donation["ledger_entry_id"], bank_transaction_id),
                )

    def donations_missing_bank_match(
        self,
        bank_account_id: int,
        month_start: date,
        month_end: date,
    ) -> list[sqlite3.Row]:
        query = """
            SELECT
                dn.*,
                d.donor_type,
                d.first_name,
                d.last_name,
                d.organization_name
            FROM donations dn
            JOIN donors d ON d.id = dn.donor_id
            WHERE
                dn.bank_account_id = ?
                AND dn.donation_date >= ?
                AND dn.donation_date <= ?
                AND NOT EXISTS (
                    SELECT 1
                    FROM bank_transactions bt
                    WHERE bt.donation_id = dn.id
                )
            ORDER BY dn.donation_date ASC, dn.id ASC
        """

        with self._connect() as connection:
            return connection.execute(
                query,
                (bank_account_id, month_start.isoformat(), month_end.isoformat()),
            ).fetchall()

    def donations_missing_ledger_link(
        self,
        bank_account_id: int,
        month_start: date,
        month_end: date,
    ) -> list[sqlite3.Row]:
        query = """
            SELECT
                dn.*,
                d.donor_type,
                d.first_name,
                d.last_name,
                d.organization_name
            FROM donations dn
            JOIN donors d ON d.id = dn.donor_id
            WHERE
                dn.bank_account_id = ?
                AND dn.donation_date >= ?
                AND dn.donation_date <= ?
                AND dn.ledger_entry_id IS NULL
            ORDER BY dn.donation_date ASC, dn.id ASC
        """

        with self._connect() as connection:
            return connection.execute(
                query,
                (bank_account_id, month_start.isoformat(), month_end.isoformat()),
            ).fetchall()

    def unmatched_bank_transactions(
        self,
        bank_account_id: int,
        month_start: date,
        month_end: date,
    ) -> list[sqlite3.Row]:
        query = """
            SELECT *
            FROM bank_transactions
            WHERE
                bank_account_id = ?
                AND transaction_date >= ?
                AND transaction_date <= ?
                AND donation_id IS NULL
            ORDER BY transaction_date ASC, id ASC
        """

        with self._connect() as connection:
            return connection.execute(
                query,
                (bank_account_id, month_start.isoformat(), month_end.isoformat()),
            ).fetchall()

    def auto_match_by_reference(
        self,
        bank_account_id: int,
        month_start: date,
        month_end: date,
    ) -> int:
        unmatched_donations = [
            row
            for row in self.donations_missing_bank_match(
                bank_account_id=bank_account_id,
                month_start=month_start,
                month_end=month_end,
            )
            if _clean(row["reference_code"])
        ]

        unmatched_transactions = [
            row
            for row in self.unmatched_bank_transactions(
                bank_account_id=bank_account_id,
                month_start=month_start,
                month_end=month_end,
            )
            if _clean(row["reference_code"])
        ]

        transaction_index: dict[str, list[sqlite3.Row]] = {}
        for transaction in unmatched_transactions:
            reference = _clean(transaction["reference_code"])
            if reference is None:
                continue
            key = reference.lower()
            transaction_index.setdefault(key, []).append(transaction)

        matched_count = 0
        for donation in unmatched_donations:
            reference = _clean(donation["reference_code"])
            if reference is None:
                continue

            candidates = transaction_index.get(reference.lower(), [])
            amount_matches = [
                candidate
                for candidate in candidates
                if candidate["amount_cents"] == donation["amount_cents"]
            ]

            if len(amount_matches) != 1:
                continue

            candidate = amount_matches[0]
            self.match_donation_to_bank_transaction(
                donation_id=donation["id"],
                bank_transaction_id=candidate["id"],
            )
            transaction_index[reference.lower()] = [
                row for row in candidates if row["id"] != candidate["id"]
            ]
            matched_count += 1

        return matched_count

    def dashboard_stats(self, today: date | None = None) -> dict[str, int | float]:
        report_date = today or date.today()
        month = month_bounds(report_date)
        year_start = date(report_date.year, 1, 1)

        with self._connect() as connection:
            donors_total = connection.execute(
                "SELECT COUNT(*) AS count FROM donors"
            ).fetchone()["count"]
            ytd_total = connection.execute(
                """
                SELECT COALESCE(SUM(amount_cents), 0) AS total
                FROM donations
                WHERE donation_date >= ?
                """,
                (year_start.isoformat(),),
            ).fetchone()["total"]
            month_total = connection.execute(
                """
                SELECT COALESCE(SUM(amount_cents), 0) AS total
                FROM donations
                WHERE donation_date >= ? AND donation_date <= ?
                """,
                (month.start.isoformat(), month.end.isoformat()),
            ).fetchone()["total"]
            month_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM donations
                WHERE donation_date >= ? AND donation_date <= ?
                """,
                (month.start.isoformat(), month.end.isoformat()),
            ).fetchone()["count"]
            month_reconciled = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM donations dn
                WHERE
                    dn.donation_date >= ?
                    AND dn.donation_date <= ?
                    AND dn.ledger_entry_id IS NOT NULL
                    AND EXISTS (
                        SELECT 1
                        FROM bank_transactions bt
                        WHERE bt.donation_id = dn.id
                    )
                """,
                (month.start.isoformat(), month.end.isoformat()),
            ).fetchone()["count"]
            unreconciled_total = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM donations dn
                WHERE
                    dn.ledger_entry_id IS NULL
                    OR NOT EXISTS (
                        SELECT 1
                        FROM bank_transactions bt
                        WHERE bt.donation_id = dn.id
                    )
                """
            ).fetchone()["count"]
            follow_ups_due = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM engagements
                WHERE follow_up_date IS NOT NULL AND follow_up_date <= ?
                """,
                (report_date.isoformat(),),
            ).fetchone()["count"]
            open_opportunities = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM donations
                WHERE COALESCE(opportunity_stage, 'Closed Won') NOT IN ('Closed Won', 'Closed Lost')
                """
            ).fetchone()["count"]
            active_campaigns = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM campaigns
                WHERE active = 1
                """
            ).fetchone()["count"]

        completion_percent = 0.0
        if month_count > 0:
            completion_percent = round((month_reconciled / month_count) * 100, 1)

        return {
            "donors_total": int(donors_total),
            "ytd_total_cents": int(ytd_total),
            "month_total_cents": int(month_total),
            "month_donation_count": int(month_count),
            "month_reconciled_count": int(month_reconciled),
            "unreconciled_total": int(unreconciled_total),
            "follow_ups_due": int(follow_ups_due),
            "open_opportunities": int(open_opportunities),
            "active_campaigns": int(active_campaigns),
            "month_completion_percent": completion_percent,
        }

    def donations_by_month(self, months: int = 12, today: date | None = None) -> list[dict[str, Any]]:
        if months <= 0:
            return []

        anchor = (today or date.today()).replace(day=1)
        start_month = _month_shift(anchor, months - 1)

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    substr(donation_date, 1, 7) AS month_key,
                    COALESCE(SUM(amount_cents), 0) AS total_cents
                FROM donations
                WHERE donation_date >= ?
                GROUP BY month_key
                ORDER BY month_key ASC
                """,
                (start_month.isoformat(),),
            ).fetchall()

        totals = {row["month_key"]: int(row["total_cents"]) for row in rows}
        output: list[dict[str, Any]] = []
        for month_offset in range(months - 1, -1, -1):
            month_start = _month_shift(anchor, month_offset)
            key = month_start.strftime("%Y-%m")
            output.append({"month_key": key, "total_cents": totals.get(key, 0)})
        return output

    def upcoming_followups(
        self,
        days: int = 30,
        today: date | None = None,
        limit: int = 25,
    ) -> list[sqlite3.Row]:
        anchor = today or date.today()
        last_day = anchor + timedelta(days=days)
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT
                    e.*,
                    d.donor_type,
                    d.first_name,
                    d.last_name,
                    d.organization_name
                FROM engagements e
                JOIN donors d ON d.id = e.donor_id
                WHERE e.follow_up_date IS NOT NULL
                    AND e.follow_up_date >= ?
                    AND e.follow_up_date <= ?
                ORDER BY e.follow_up_date ASC, e.id ASC
                LIMIT ?
                """,
                (anchor.isoformat(), last_day.isoformat(), limit),
            ).fetchall()

    def reconciliation_snapshot(
        self,
        bank_account_id: int,
        month_start: date,
        month_end: date,
    ) -> dict[str, int | float]:
        with self._connect() as connection:
            donations_total_row = connection.execute(
                """
                SELECT
                    COUNT(*) AS count,
                    COALESCE(SUM(amount_cents), 0) AS total
                FROM donations
                WHERE
                    bank_account_id = ?
                    AND donation_date >= ?
                    AND donation_date <= ?
                """,
                (bank_account_id, month_start.isoformat(), month_end.isoformat()),
            ).fetchone()
            bank_total_row = connection.execute(
                """
                SELECT
                    COUNT(*) AS count,
                    COALESCE(SUM(amount_cents), 0) AS total
                FROM bank_transactions
                WHERE
                    bank_account_id = ?
                    AND transaction_date >= ?
                    AND transaction_date <= ?
                """,
                (bank_account_id, month_start.isoformat(), month_end.isoformat()),
            ).fetchone()
            fully_reconciled_row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM donations dn
                WHERE
                    dn.bank_account_id = ?
                    AND dn.donation_date >= ?
                    AND dn.donation_date <= ?
                    AND dn.ledger_entry_id IS NOT NULL
                    AND EXISTS (
                        SELECT 1
                        FROM bank_transactions bt
                        WHERE bt.donation_id = dn.id
                    )
                """,
                (bank_account_id, month_start.isoformat(), month_end.isoformat()),
            ).fetchone()

        donation_count = int(donations_total_row["count"])
        donation_total = int(donations_total_row["total"])
        bank_count = int(bank_total_row["count"])
        bank_total = int(bank_total_row["total"])
        fully_reconciled = int(fully_reconciled_row["count"])

        missing_bank_count = len(
            self.donations_missing_bank_match(
                bank_account_id=bank_account_id,
                month_start=month_start,
                month_end=month_end,
            )
        )
        missing_ledger_count = len(
            self.donations_missing_ledger_link(
                bank_account_id=bank_account_id,
                month_start=month_start,
                month_end=month_end,
            )
        )
        unmatched_bank_transactions_count = len(
            self.unmatched_bank_transactions(
                bank_account_id=bank_account_id,
                month_start=month_start,
                month_end=month_end,
            )
        )

        completion_percent = 0.0
        if donation_count > 0:
            completion_percent = round((fully_reconciled / donation_count) * 100, 1)

        return {
            "donation_count": donation_count,
            "donation_total_cents": donation_total,
            "bank_transaction_count": bank_count,
            "bank_total_cents": bank_total,
            "fully_reconciled_count": fully_reconciled,
            "missing_bank_count": missing_bank_count,
            "missing_ledger_count": missing_ledger_count,
            "unmatched_bank_transactions_count": unmatched_bank_transactions_count,
            "variance_cents": donation_total - bank_total,
            "completion_percent": completion_percent,
        }
