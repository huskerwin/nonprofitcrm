"""Streamlit app for nonprofit donor and reconciliation management."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

from nonprofit_crm import (
    CRMStore,
    HipaaSensitivityScanner,
    cents_from_amount,
    donor_display_name,
    format_currency,
    month_bounds,
)


DONOR_STAGES = [
    "Prospect",
    "Active",
    "Major Donor",
    "Foundation",
    "Lapsed",
]

ENGAGEMENT_TYPES = [
    "Call",
    "Email",
    "Meeting",
    "Site Visit",
    "Event",
    "Volunteer Touchpoint",
    "Thank You",
]

ENGAGEMENT_CHANNELS = ["In Person", "Phone", "Email", "Text", "Video", "Social"]

DONATION_TYPES = ["One-time", "Recurring", "Grant", "Matching Gift", "In-kind"]
PAYMENT_METHODS = ["ACH", "Wire", "Check", "Credit Card", "Cash", "Stock"]
OPPORTUNITY_STAGES = [
    "Prospecting",
    "Cultivation",
    "Pledged",
    "Closed Won",
    "Closed Lost",
]
CAMPAIGN_TYPES = ["Fundraising", "Peer-to-Peer", "Corporate", "Event", "Grant"]
CAMPAIGN_STATUSES = ["Planned", "In Progress", "Completed", "On Hold"]

DB_PATH = Path(".data/nonprofit_crm.db")
STORE = CRMStore(DB_PATH)
HIPAA_SCANNER = HipaaSensitivityScanner()


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Public+Sans:wght@400;500;600;700&display=swap');

          :root {
            --sf-blue-700: #032d60;
            --sf-blue-600: #0176d3;
            --sf-blue-500: #0b5cab;
            --sf-cloud-100: #f3f2f2;
            --sf-cloud-200: #eef1f6;
            --sf-card: #ffffff;
            --sf-text: #181818;
            --sf-muted: #3e3e3c;
            --sf-border: #c9c7c5;
          }

          .stApp {
            background:
              radial-gradient(circle at 88% -15%, rgba(1, 118, 211, 0.16), transparent 30%),
              radial-gradient(circle at 8% -12%, rgba(3, 45, 96, 0.12), transparent 34%),
              linear-gradient(170deg, var(--sf-cloud-100) 0%, var(--sf-cloud-200) 56%, #f8fbff 100%);
            color: var(--sf-text);
          }

          .stApp,
          .stApp p,
          .stApp span,
          .stApp label,
          .stApp li,
          .stApp small,
          .stApp div[data-testid="stMetricLabel"],
          .stApp div[data-testid="stMetricValue"],
          .stApp div[data-testid="stMarkdownContainer"] {
            color: var(--sf-text);
          }

          html, body, [class*="css"] {
            font-family: "Public Sans", "Trebuchet MS", sans-serif;
          }

          [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff 0%, #f4f6fa 100%);
            border-right: 1px solid rgba(201, 199, 197, 0.55);
          }

          .block-container {
            padding-top: 1.1rem;
            padding-bottom: 1.8rem;
          }

          .crm-hero {
            background: linear-gradient(124deg, var(--sf-blue-700), var(--sf-blue-600));
            border-radius: 18px;
            color: #ffffff;
            padding: 1.2rem 1.25rem;
            box-shadow: 0 16px 30px rgba(3, 45, 96, 0.28);
            margin-bottom: 1rem;
          }

          .crm-hero,
          .crm-hero h1,
          .crm-hero p {
            color: #ffffff !important;
          }

          .crm-hero h1 {
            margin: 0;
            font-family: "Space Grotesk", "Arial Black", sans-serif;
            font-size: clamp(1.45rem, 2.6vw, 2.2rem);
            line-height: 1.2;
            letter-spacing: 0.015em;
          }

          .crm-hero p {
            margin: 0.55rem 0 0;
            max-width: 78ch;
            font-weight: 500;
            opacity: 0.93;
          }

          .object-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.8rem;
          }

          .object-pill {
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.3);
            padding: 0.24rem 0.72rem;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.02em;
          }

          .metric-card {
            border-radius: 14px;
            border: 1px solid rgba(201, 199, 197, 0.6);
            background: var(--sf-card);
            box-shadow: 0 6px 14px rgba(24, 24, 24, 0.06);
            padding: 0.75rem 0.8rem;
            min-height: 108px;
          }

          .metric-label {
            margin: 0;
            color: var(--sf-muted);
            font-weight: 600;
            font-size: 0.84rem;
          }

          .metric-value {
            margin: 0.3rem 0 0;
            color: var(--sf-blue-700);
            font-family: "Space Grotesk", "Arial Black", sans-serif;
            font-size: 1.45rem;
            line-height: 1.1;
            letter-spacing: 0.01em;
          }

          .metric-sub {
            margin: 0.4rem 0 0;
            color: #5a5a58;
            font-size: 0.82rem;
            font-weight: 500;
          }

          .section-note {
            color: #555453;
            font-weight: 500;
            margin-top: -0.2rem;
            margin-bottom: 0.8rem;
          }

          .stButton > button {
            background: linear-gradient(120deg, var(--sf-blue-500), var(--sf-blue-600));
            color: #ffffff;
            border: 1px solid #0b4f97;
            border-radius: 0.6rem;
            font-weight: 600;
          }

          .stTextInput input,
          .stTextArea textarea,
          .stNumberInput input,
          .stDateInput input,
          div[data-baseweb="select"] * {
            color: var(--sf-text) !important;
          }

          .stDataFrame,
          .stDataFrame * {
            color: var(--sf-text) !important;
          }

          .stButton > button:hover {
            border-color: var(--sf-blue-700);
            box-shadow: 0 8px 16px rgba(11, 92, 171, 0.22);
          }

          button[data-baseweb="tab"] {
            color: #555453;
          }

          button[data-baseweb="tab"][aria-selected="true"] {
            color: var(--sf-blue-700);
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_metric_card(title: str, value: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
          <p class="metric-label">{title}</p>
          <p class="metric-value">{value}</p>
          <p class="metric-sub">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _hero() -> None:
    st.markdown(
        """
        <div class="crm-hero">
          <h1>Harborlight Nonprofit Cloud Workspace</h1>
          <p>
            Salesforce Nonprofit Cloud-inspired operations center for Accounts, Contacts, Opportunities,
            Campaigns, Engagement Plans, Gift Entry, and monthly finance reconciliation.
          </p>
          <div class="object-row">
            <span class="object-pill">Home</span>
            <span class="object-pill">Accounts</span>
            <span class="object-pill">Contacts</span>
            <span class="object-pill">Opportunities</span>
            <span class="object-pill">Campaigns</span>
            <span class="object-pill">Engagement Plans</span>
            <span class="object-pill">Gift Entry</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _donor_option_label(row: dict) -> str:
    return f"{donor_display_name(row)} (#{row['id']})"


def _bank_account_option_label(row: dict) -> str:
    pieces = [row["name"]]
    if row["bank_name"]:
        pieces.append(str(row["bank_name"]))
    if row["account_last4"]:
        pieces.append(f"****{row['account_last4']}")
    return " | ".join(pieces)


def _ledger_option_label(row: dict) -> str:
    amount = format_currency(int(row["amount_cents"]))
    return f"#{row['id']} {row['posted_date']} {amount} - {row['description']}"


def _campaign_option_label(row: dict) -> str:
    raised = format_currency(int(row.get("raised_cents") or 0))
    return f"{row['name']} (Raised {raised})"


def _bank_tx_option_label(row: dict) -> str:
    amount = format_currency(int(row["amount_cents"]))
    return f"#{row['id']} {row['transaction_date']} {amount} - {row['description']}"


def _table_or_info(frame: pd.DataFrame, empty_message: str) -> None:
    if frame.empty:
        st.info(empty_message)
        return
    st.dataframe(frame, use_container_width=True, hide_index=True)


def _rows_to_dicts(rows: Iterable) -> list[dict]:
    return [dict(row) for row in rows]


def _render_home_people_search() -> None:
    if "home_people_search_open" not in st.session_state:
        st.session_state.home_people_search_open = False

    left, right = st.columns([5, 1], gap="small")
    with left:
        st.markdown("### Home")
    with right:
        label = "Close Search" if st.session_state.home_people_search_open else "Search"
        if st.button(label, key="home-people-search-toggle", use_container_width=True):
            st.session_state.home_people_search_open = not st.session_state.home_people_search_open

    if not st.session_state.home_people_search_open:
        return

    st.markdown(
        "<p class='section-note'>Search people in Accounts & Contacts by name, email, or phone.</p>",
        unsafe_allow_html=True,
    )

    search_term = st.text_input(
        "People Search",
        key="home-people-search-term",
        placeholder="e.g. Avery Mills or avery@example.org",
    ).strip()

    if not search_term:
        st.info("Enter a search term to find people.")
        return

    matches = _rows_to_dicts(STORE.list_donors(search_term=search_term, smart_search=True))
    people_matches = [row for row in matches if row["donor_type"] == "Individual"]

    search_results_df = pd.DataFrame(
        [
            {
                "Name": donor_display_name(row),
                "Email": row.get("email") or "-",
                "Phone": row.get("phone") or "-",
                "Owner": row.get("relationship_manager") or "Unassigned",
                "Lifecycle": row["lifecycle_stage"],
                "Last Close Date": row.get("last_donation_date") or "-",
            }
            for row in people_matches
        ]
    )
    _table_or_info(search_results_df, "No people matched your search.")


def render_dashboard() -> None:
    _render_home_people_search()

    stats = STORE.dashboard_stats()
    metric_columns = st.columns(6)

    with metric_columns[0]:
        _render_metric_card("Accounts & Contacts", str(stats["donors_total"]), "Constituent records")
    with metric_columns[1]:
        _render_metric_card(
            "Open Opportunities",
            str(int(stats["open_opportunities"])),
            "Prospecting, cultivation, and pledged gifts",
        )
    with metric_columns[2]:
        _render_metric_card(
            "This Month Raised",
            format_currency(int(stats["month_total_cents"])),
            f"{stats['month_donation_count']} opportunities posted",
        )
    with metric_columns[3]:
        _render_metric_card(
            "Year-to-Date Raised",
            format_currency(int(stats["ytd_total_cents"])),
            "Closed revenue",
        )
    with metric_columns[4]:
        _render_metric_card(
            "Active Campaigns",
            str(int(stats["active_campaigns"])),
            "Running fundraising initiatives",
        )
    with metric_columns[5]:
        _render_metric_card(
            "Reconciliation Rate",
            f"{stats['month_completion_percent']}%",
            f"{stats['month_reconciled_count']} gifts fully matched",
        )

    st.markdown("### Performance Pulse")
    st.markdown(
        "<p class='section-note'>Salesforce-style home view for pipeline, activity, and exceptions.</p>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.3, 1], gap="large")
    monthly_giving_rows = STORE.donations_by_month(months=12)
    monthly_df = pd.DataFrame(monthly_giving_rows)
    if not monthly_df.empty:
        monthly_df["month"] = pd.to_datetime(monthly_df["month_key"] + "-01")
        monthly_df["donation_amount"] = monthly_df["total_cents"] / 100
        monthly_df = monthly_df.set_index("month")

    with left:
        st.markdown("#### Donations by Month")
        if monthly_df.empty:
            st.info("No donation records yet. Add gifts to populate trends.")
        else:
            st.bar_chart(monthly_df["donation_amount"], color="#0176D3")

    with right:
        st.markdown("#### Opportunity Pipeline")
        pipeline_rows = _rows_to_dicts(STORE.opportunity_pipeline())
        if pipeline_rows:
            pipeline_df = pd.DataFrame(pipeline_rows)
            pipeline_df["amount"] = pipeline_df["total_cents"] / 100
            pipeline_df = pipeline_df.set_index("stage_name")
            st.bar_chart(pipeline_df["amount"], color="#0B5CAB")

            pipeline_grid = pd.DataFrame(
                [
                    {
                        "Stage": row["stage_name"],
                        "Count": int(row["opportunity_count"]),
                        "Amount": format_currency(int(row["total_cents"])),
                    }
                    for row in pipeline_rows
                ]
            )
            _table_or_info(pipeline_grid, "No opportunity data available.")
        else:
            st.info("No opportunities recorded yet.")

    followups, unreconciled = st.columns(2, gap="large")

    with followups:
        st.markdown("#### Engagement Plan Tasks Due")
        upcoming = _rows_to_dicts(STORE.upcoming_followups(days=30))
        upcoming_df = pd.DataFrame(
            [
                {
                    "Due": row["follow_up_date"],
                    "Account/Contact": donor_display_name(row),
                    "Owner": row.get("owner") or "Unassigned",
                    "Task": row["summary"],
                }
                for row in upcoming
            ]
        )
        _table_or_info(upcoming_df, "No engagement plan tasks due in the next 30 days.")

    with unreconciled:
        st.markdown("#### Finance Exceptions")
        exception_rows = _rows_to_dicts(STORE.list_donations(unreconciled_only=True))
        exception_df = pd.DataFrame(
            [
                {
                    "Close Date": row.get("close_date") or row["donation_date"],
                    "Opportunity": row.get("opportunity_name") or f"Donation #{row['id']}",
                    "Account/Contact": donor_display_name(row),
                    "Amount": format_currency(int(row["amount_cents"])),
                    "Ledger": "Linked" if row["has_ledger_link"] else "Missing",
                    "Bank": "Matched" if row["has_bank_match"] else "Missing",
                }
                for row in exception_rows[:20]
            ]
        )
        _table_or_info(exception_df, "All posted donations are reconciled.")


def render_donors_tab() -> None:
    st.markdown("### Accounts & Contacts")
    st.markdown(
        "<p class='section-note'>Salesforce-style constituent records with related opportunities and engagement history.</p>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1, 1.3], gap="large")

    with left:
        st.markdown("#### Create Account or Contact")
        with st.form("donor-create-form", clear_on_submit=True):
            donor_type = st.radio(
                "Record Type",
                options=["Individual", "Organization"],
                horizontal=True,
            )

            first_name = ""
            last_name = ""
            organization_name = ""

            if donor_type == "Individual":
                first_name = st.text_input("First Name *")
                last_name = st.text_input("Last Name *")
            else:
                organization_name = st.text_input("Organization Name *")

            email = st.text_input("Email")
            phone = st.text_input("Phone")
            relationship_manager = st.text_input("Relationship Manager")
            lifecycle_stage = st.selectbox("Lifecycle Stage", DONOR_STAGES)
            preferred_channel = st.selectbox(
                "Preferred Contact Channel",
                ["Email", "Phone", "Text", "In Person", "Mail", "None"],
            )
            notes = st.text_area("Profile Notes", height=110)

            submit = st.form_submit_button("Create Record", use_container_width=True)
            if submit:
                try:
                    STORE.add_donor(
                        donor_type=donor_type,
                        first_name=first_name,
                        last_name=last_name,
                        organization_name=organization_name,
                        email=email,
                        phone=phone,
                        lifecycle_stage=lifecycle_stage,
                        relationship_manager=relationship_manager,
                        preferred_channel=preferred_channel,
                        notes=notes,
                    )
                    st.success("Record created.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    with right:
        search_term = st.text_input("Search Accounts/Contacts", placeholder="Name, organization, or email")
        donor_rows = _rows_to_dicts(STORE.list_donors(search_term=search_term, smart_search=True))

        directory_df = pd.DataFrame(
            [
                {
                    "ID": row["id"],
                    "Account / Contact": donor_display_name(row),
                    "Type": row["donor_type"],
                    "Owner": row.get("relationship_manager") or "Unassigned",
                    "Lifecycle": row["lifecycle_stage"],
                    "Lifetime Closed Won": format_currency(int(row["total_given_cents"])),
                    "Last Closed Date": row.get("last_donation_date") or "-",
                    "Engagement Tasks": int(row["engagement_count"]),
                    "Email": row.get("email") or "-",
                }
                for row in donor_rows
            ]
        )
        _table_or_info(directory_df, "No records yet. Add your first account or contact.")

        if donor_rows:
            donor_map = {row["id"]: row for row in donor_rows}
            selected_id = st.selectbox(
                "Open Record",
                options=list(donor_map.keys()),
                format_func=lambda donor_id: _donor_option_label(donor_map[donor_id]),
            )
            selected = donor_map[selected_id]

            profile_cols = st.columns(3)
            with profile_cols[0]:
                st.metric("Lifetime Closed Won", format_currency(int(selected["total_given_cents"])))
            with profile_cols[1]:
                st.metric("Engagement Tasks", str(int(selected["engagement_count"])))
            with profile_cols[2]:
                st.metric("Last Close Date", selected.get("last_donation_date") or "-")

            st.caption(
                f"Contact: {selected.get('email') or '-'} | {selected.get('phone') or '-'} | "
                f"Manager: {selected.get('relationship_manager') or 'Unassigned'}"
            )

            donor_donations = _rows_to_dicts(STORE.list_donations(donor_id=selected_id))
            donor_engagements = _rows_to_dicts(STORE.list_engagements(donor_id=selected_id, limit=25))

            history_left, history_right = st.columns(2, gap="large")
            with history_left:
                st.markdown("##### Related Opportunities")
                donation_history_df = pd.DataFrame(
                    [
                        {
                            "Close Date": row.get("close_date") or row["donation_date"],
                            "Opportunity": row.get("opportunity_name") or f"Donation #{row['id']}",
                            "Amount": format_currency(int(row["amount_cents"])),
                            "Stage": row.get("opportunity_stage") or "Closed Won",
                            "Campaign": row.get("campaign_label") or row.get("campaign") or "-",
                            "Ledger": "Yes" if row["has_ledger_link"] else "No",
                            "Bank Match": "Yes" if row["has_bank_match"] else "No",
                        }
                        for row in donor_donations[:15]
                    ]
                )
                _table_or_info(donation_history_df, "No opportunities for this record yet.")

            with history_right:
                st.markdown("##### Engagement Plan Timeline")
                engagement_history_df = pd.DataFrame(
                    [
                        {
                            "Date": row["engagement_date"],
                            "Type": row["engagement_type"],
                            "Channel": row.get("channel") or "-",
                            "Owner": row.get("owner") or "Unassigned",
                            "Summary": row["summary"],
                            "Follow-up": row.get("follow_up_date") or "-",
                        }
                        for row in donor_engagements
                    ]
                )
                _table_or_info(engagement_history_df, "No engagement tasks for this record yet.")


def render_engagements_tab() -> None:
    st.markdown("### Engagement Plans")
    st.markdown(
        "<p class='section-note'>Track stewardship tasks, activity history, and follow-up commitments.</p>",
        unsafe_allow_html=True,
    )

    donor_rows = _rows_to_dicts(STORE.list_donors())
    if not donor_rows:
        st.info("Create at least one account/contact before logging engagement tasks.")
        return

    donor_map = {row["id"]: row for row in donor_rows}

    with st.form("engagement-form", clear_on_submit=True):
        first_col, second_col = st.columns(2)
        with first_col:
            donor_id = st.selectbox(
                "Donor",
                options=list(donor_map.keys()),
                format_func=lambda item_id: _donor_option_label(donor_map[item_id]),
            )
            engagement_date = st.date_input("Engagement Date", value=date.today())
            engagement_type = st.selectbox("Engagement Type", ENGAGEMENT_TYPES)
            channel = st.selectbox("Channel", ENGAGEMENT_CHANNELS)

        with second_col:
            owner = st.text_input("Owner")
            summary = st.text_area("Summary *", height=100)
            next_step = st.text_area("Next Step", height=70)
            has_follow_up = st.checkbox("Set follow-up date", value=True)
            follow_up_date = (
                st.date_input("Follow-up Date", value=date.today()) if has_follow_up else None
            )

        save = st.form_submit_button("Create Task", use_container_width=True)
        if save:
            try:
                STORE.add_engagement(
                    donor_id=donor_id,
                    engagement_date=engagement_date,
                    engagement_type=engagement_type,
                    channel=channel,
                    summary=summary,
                    next_step=next_step,
                    follow_up_date=follow_up_date,
                    owner=owner,
                )
                st.success("Engagement task logged.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    st.markdown("#### Task List View")
    records = _rows_to_dicts(STORE.list_engagements(limit=300))

    type_filter = st.selectbox("Filter by Type", ["All"] + ENGAGEMENT_TYPES)
    owner_filter = st.text_input("Filter by Owner")

    filtered = []
    for row in records:
        if type_filter != "All" and row["engagement_type"] != type_filter:
            continue
        if owner_filter.strip() and owner_filter.lower() not in (row.get("owner") or "").lower():
            continue
        filtered.append(row)

    engagements_df = pd.DataFrame(
        [
            {
                "Date": row["engagement_date"],
                "Account/Contact": donor_display_name(row),
                "Type": row["engagement_type"],
                "Channel": row.get("channel") or "-",
                "Owner": row.get("owner") or "Unassigned",
                "Task": row["summary"],
                "Due Date": row.get("follow_up_date") or "-",
            }
            for row in filtered
        ]
    )
    _table_or_info(engagements_df, "No engagement plan tasks match the current filters.")


def render_donations_tab() -> None:
    st.markdown("### Opportunities")
    st.markdown(
        "<p class='section-note'>Gift Opportunity management inspired by Salesforce NPSP Opportunity records.</p>",
        unsafe_allow_html=True,
    )

    donors = _rows_to_dicts(STORE.list_donors())
    accounts = _rows_to_dicts(STORE.list_bank_accounts(active_only=True))
    campaigns = _rows_to_dicts(STORE.list_campaigns(active_only=True))
    unlinked_ledger = _rows_to_dicts(STORE.list_ledger_entries(unlinked_only=True))

    if not donors:
        st.info("Create account/contact records first, then add opportunities.")
        return

    donor_map = {row["id"]: row for row in donors}
    account_map = {row["id"]: row for row in accounts}
    campaign_map = {row["id"]: row for row in campaigns}
    ledger_map = {row["id"]: row for row in unlinked_ledger}

    with st.form("opportunity-create-form", clear_on_submit=True):
        left, right = st.columns(2)
        with left:
            donor_id = st.selectbox(
                "Account/Contact",
                options=list(donor_map.keys()),
                format_func=lambda item_id: _donor_option_label(donor_map[item_id]),
            )
            opportunity_name = st.text_input("Opportunity Name *")
            close_date = st.date_input("Close Date", value=date.today())
            opportunity_stage = st.selectbox("Stage", OPPORTUNITY_STAGES, index=3)
            probability_percent = st.slider("Probability %", min_value=0, max_value=100, value=100)
            amount = st.number_input("Amount", min_value=1.0, step=25.0, format="%.2f")

        with right:
            donation_type = st.selectbox("Gift Type", DONATION_TYPES)
            selected_campaign_id = st.selectbox(
                "Primary Campaign",
                options=[None] + list(campaign_map.keys()),
                format_func=(
                    lambda item_id: "None"
                    if item_id is None
                    else _campaign_option_label(campaign_map[item_id])
                ),
            )
            campaign_text = st.text_input("Campaign Label (fallback)")
            fund = st.text_input("Fund / Restriction")
            payment_method = st.selectbox("Payment Method", PAYMENT_METHODS)
            reference_code = st.text_input("Reference Code")
            selected_bank_account = st.selectbox(
                "Bank Account",
                options=[None] + list(account_map.keys()),
                format_func=(
                    lambda item_id: "Unassigned"
                    if item_id is None
                    else _bank_account_option_label(account_map[item_id])
                ),
            )
            selected_ledger_entry = st.selectbox(
                "Ledger Entry (Optional)",
                options=[None] + list(ledger_map.keys()),
                format_func=(
                    lambda item_id: "None"
                    if item_id is None
                    else _ledger_option_label(ledger_map[item_id])
                ),
            )

        notes = st.text_area("Internal Notes", height=80)
        is_anonymous = st.checkbox("Anonymous gift")
        save = st.form_submit_button("Create Opportunity", use_container_width=True)
        if save:
            try:
                STORE.add_donation(
                    donor_id=donor_id,
                    donation_date=close_date,
                    amount_cents=cents_from_amount(float(amount)),
                    donation_type=donation_type,
                    campaign=campaign_text,
                    fund=fund,
                    payment_method=payment_method,
                    reference_code=reference_code,
                    bank_account_id=selected_bank_account,
                    ledger_entry_id=selected_ledger_entry,
                    notes=notes,
                    is_anonymous=is_anonymous,
                    opportunity_name=opportunity_name,
                    opportunity_stage=opportunity_stage,
                    close_date=close_date,
                    campaign_id=selected_campaign_id,
                    probability_percent=probability_percent,
                )
                st.success("Opportunity created.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    all_donations = _rows_to_dicts(STORE.list_donations())
    open_opportunities = [
        row
        for row in all_donations
        if row.get("opportunity_stage") not in {"Closed Won", "Closed Lost"}
    ]

    st.markdown("#### Stage Management")
    if open_opportunities:
        opportunity_map = {row["id"]: row for row in open_opportunities}
        stage_cols = st.columns([1.5, 0.9, 0.9, 0.7])
        with stage_cols[0]:
            stage_donation_id = st.selectbox(
                "Opportunity",
                options=list(opportunity_map.keys()),
                format_func=lambda item_id: (
                    f"#{item_id} {opportunity_map[item_id].get('opportunity_name') or f'Donation {item_id}'}"
                ),
                key="opportunity-stage-record",
            )
        selected_record = opportunity_map[stage_donation_id]
        with stage_cols[1]:
            current_stage = selected_record.get("opportunity_stage") or "Prospecting"
            stage_index = OPPORTUNITY_STAGES.index(current_stage) if current_stage in OPPORTUNITY_STAGES else 0
            next_stage = st.selectbox(
                "New Stage",
                options=OPPORTUNITY_STAGES,
                index=stage_index,
                key="opportunity-stage-value",
            )
        with stage_cols[2]:
            next_probability = st.slider(
                "Probability",
                min_value=0,
                max_value=100,
                value=int(selected_record.get("probability_percent") or 0),
                key="opportunity-stage-probability",
            )
        with stage_cols[3]:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Update", use_container_width=True):
                STORE.update_opportunity_stage(
                    donation_id=stage_donation_id,
                    stage_name=next_stage,
                    probability_percent=next_probability,
                )
                st.success("Opportunity stage updated.")
                st.rerun()
    else:
        st.info("No open opportunities to update.")

    missing_ledger = [row for row in all_donations if not row["has_ledger_link"]]
    current_unlinked_ledger = _rows_to_dicts(STORE.list_ledger_entries(unlinked_only=True))

    if missing_ledger and current_unlinked_ledger:
        st.markdown("#### Quick Ledger Linking")
        miss_map = {row["id"]: row for row in missing_ledger}
        link_ledger_map = {row["id"]: row for row in current_unlinked_ledger}
        c1, c2, c3 = st.columns([1, 1.3, 0.7])
        with c1:
            donation_choice = st.selectbox(
                "Opportunity",
                options=list(miss_map.keys()),
                format_func=lambda item_id: (
                    f"#{item_id} | {format_currency(int(miss_map[item_id]['amount_cents']))} | "
                    f"{miss_map[item_id].get('opportunity_name') or donor_display_name(miss_map[item_id])}"
                ),
                key="opportunity-ledger-link-donation",
            )
        with c2:
            selected_donation = miss_map[donation_choice]
            amount_matched_ledger = [
                row
                for row in current_unlinked_ledger
                if row["amount_cents"] == selected_donation["amount_cents"]
            ]
            candidate_ledger = amount_matched_ledger or current_unlinked_ledger
            ledger_choice = st.selectbox(
                "Ledger Entry",
                options=[row["id"] for row in candidate_ledger],
                format_func=lambda item_id: _ledger_option_label(link_ledger_map[item_id]),
                key="opportunity-ledger-link-ledger",
            )
        with c3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Link", use_container_width=True):
                STORE.link_donation_to_ledger(donation_choice, ledger_choice)
                st.success("Opportunity linked to ledger entry.")
                st.rerun()

    st.markdown("#### Opportunity List View")
    donation_df = pd.DataFrame(
        [
            {
                "Close Date": row.get("close_date") or row["donation_date"],
                "Opportunity": row.get("opportunity_name") or f"Donation #{row['id']}",
                "Account/Contact": donor_display_name(row),
                "Stage": row.get("opportunity_stage") or "Closed Won",
                "Probability": f"{int(row.get('probability_percent') or 0)}%",
                "Amount": format_currency(int(row["amount_cents"])),
                "Gift Type": row["donation_type"],
                "Campaign": row.get("campaign_label") or row.get("campaign") or "-",
                "Fund": row.get("fund") or "-",
                "Payment": row.get("payment_method") or "-",
                "Bank": row.get("bank_account_name") or "Unassigned",
                "Ledger": "Linked" if row["has_ledger_link"] else "Missing",
                "Bank Match": "Matched" if row["has_bank_match"] else "Missing",
                "Reference": row.get("reference_code") or "-",
            }
            for row in all_donations
        ]
    )
    _table_or_info(donation_df, "No opportunities recorded yet.")


def render_campaigns_tab() -> None:
    st.markdown("### Campaigns")
    st.markdown(
        "<p class='section-note'>Build campaign hierarchy, track performance, and align opportunities to each initiative.</p>",
        unsafe_allow_html=True,
    )

    campaign_rows = _rows_to_dicts(STORE.list_campaigns(active_only=False))
    campaign_map = {row["id"]: row for row in campaign_rows}

    left, right = st.columns([1, 1.4], gap="large")

    with left:
        with st.form("campaign-create-form", clear_on_submit=True):
            name = st.text_input("Campaign Name *")
            campaign_type = st.selectbox("Type", CAMPAIGN_TYPES)
            status = st.selectbox("Status", CAMPAIGN_STATUSES)
            owner = st.text_input("Owner")
            start_date = st.date_input("Start Date", value=date.today())
            end_date = st.date_input("End Date", value=date.today())
            goal_amount = st.number_input("Goal Amount", min_value=0.0, value=5000.0, step=250.0, format="%.2f")
            parent_campaign = st.selectbox(
                "Parent Campaign",
                options=[None] + list(campaign_map.keys()),
                format_func=(
                    lambda item_id: "None"
                    if item_id is None
                    else campaign_map[item_id]["name"]
                ),
            )
            description = st.text_area("Description", height=90)

            save = st.form_submit_button("Create Campaign", use_container_width=True)
            if save:
                try:
                    STORE.add_campaign(
                        name=name,
                        campaign_type=campaign_type,
                        status=status,
                        owner=owner,
                        start_date=start_date,
                        end_date=end_date,
                        goal_cents=cents_from_amount(float(goal_amount)),
                        parent_campaign_id=parent_campaign,
                        description=description,
                    )
                    st.success("Campaign created.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    with right:
        refreshed_campaigns = _rows_to_dicts(STORE.list_campaigns(active_only=False))
        campaign_df = pd.DataFrame(
            [
                {
                    "Campaign": row["name"],
                    "Type": row["campaign_type"],
                    "Status": row["status"],
                    "Owner": row.get("owner") or "Unassigned",
                    "Parent": row.get("parent_campaign_name") or "-",
                    "Goal": format_currency(int(row["goal_cents"])),
                    "Raised": format_currency(int(row["raised_cents"])),
                    "Gift Count": int(row["gift_count"]),
                    "Progress": (
                        f"{round((int(row['raised_cents']) / int(row['goal_cents'])) * 100, 1)}%"
                        if int(row["goal_cents"]) > 0
                        else "-"
                    ),
                }
                for row in refreshed_campaigns
            ]
        )
        _table_or_info(campaign_df, "No campaigns yet. Create your first campaign.")

    st.markdown("#### Campaign Influence (Opportunities)")
    all_donations = _rows_to_dicts(STORE.list_donations())
    if not all_donations:
        st.info("No opportunities recorded yet.")
        return

    influence_rollup: dict[str, dict[str, int]] = {}
    for row in all_donations:
        campaign_name = row.get("campaign_label") or row.get("campaign") or "No Campaign"
        entry = influence_rollup.setdefault(campaign_name, {"count": 0, "total": 0})
        entry["count"] += 1
        entry["total"] += int(row["amount_cents"])

    influence_df = pd.DataFrame(
        [
            {
                "Campaign": campaign_name,
                "Opportunities": data["count"],
                "Total Amount": format_currency(data["total"]),
            }
            for campaign_name, data in sorted(
                influence_rollup.items(),
                key=lambda item: item[1]["total"],
                reverse=True,
            )
        ]
    )
    _table_or_info(influence_df, "No campaign-linked opportunities yet.")


def render_ledger_tab() -> None:
    st.markdown("### Gift Entry & Ledger")
    st.markdown(
        "<p class='section-note'>Gift Entry-style journal workspace for accounting sync and audit-ready posting.</p>",
        unsafe_allow_html=True,
    )

    with st.form("ledger-entry-form", clear_on_submit=True):
        left, right = st.columns(2)
        with left:
            posted_date = st.date_input("Posted Date", value=date.today())
            account_code = st.text_input("Account Code", value="4000-DONATIONS")
            source = st.selectbox("Source", ["Manual", "Accounting Export", "ERP Sync"])
        with right:
            description = st.text_input("Description")
            amount = st.number_input("Amount", value=100.0, step=25.0, format="%.2f")
            reference_code = st.text_input("Reference Code")

        save = st.form_submit_button("Create Journal Entry", use_container_width=True)
        if save:
            try:
                STORE.add_ledger_entry(
                    posted_date=posted_date,
                    account_code=account_code,
                    description=description,
                    amount_cents=cents_from_amount(float(amount)),
                    reference_code=reference_code,
                    source=source,
                )
                st.success("Journal entry created.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    filter_month = st.date_input("Ledger Month", value=date.today().replace(day=1), key="ledger-month-filter")
    bounds = month_bounds(filter_month)
    ledger_rows = _rows_to_dicts(
        STORE.list_ledger_entries(month_start=bounds.start, month_end=bounds.end)
    )
    total_cents = sum(int(row["amount_cents"]) for row in ledger_rows)
    st.metric("Month Total", format_currency(total_cents))

    ledger_df = pd.DataFrame(
        [
            {
                "Posted": row["posted_date"],
                "Account": row["account_code"],
                "Description": row["description"],
                "Amount": format_currency(int(row["amount_cents"])),
                "Reference": row.get("reference_code") or "-",
                "Source": row.get("source") or "Manual",
                "Linked Donations": int(row["linked_donations"]),
            }
            for row in ledger_rows
        ]
    )
    _table_or_info(ledger_df, "No ledger entries found for this month.")


def render_reconciliation_tab() -> None:
    st.markdown("### Reconciliation")
    st.markdown(
        "<p class='section-note'>Close the loop between opportunities, bank deposits, and accounting records each month.</p>",
        unsafe_allow_html=True,
    )

    setup_col, transaction_col = st.columns([1, 1.3], gap="large")

    with setup_col:
        st.markdown("#### Bank Accounts")
        with st.form("bank-account-form", clear_on_submit=True):
            name = st.text_input("Account Name")
            bank_name = st.text_input("Bank Name")
            account_last4 = st.text_input("Last 4 Digits")
            add_account = st.form_submit_button("Add Account", use_container_width=True)
            if add_account:
                try:
                    STORE.add_bank_account(
                        name=name,
                        bank_name=bank_name,
                        account_last4=account_last4,
                    )
                    st.success("Bank account added.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

        accounts = _rows_to_dicts(STORE.list_bank_accounts(active_only=False))
        account_df = pd.DataFrame(
            [
                {
                    "ID": row["id"],
                    "Account": row["name"],
                    "Bank": row.get("bank_name") or "-",
                    "Last4": row.get("account_last4") or "-",
                    "Currency": row["currency"],
                    "Active": "Yes" if row["active"] else "No",
                }
                for row in accounts
            ]
        )
        _table_or_info(account_df, "No bank accounts available.")

    with transaction_col:
        accounts = _rows_to_dicts(STORE.list_bank_accounts(active_only=True))
        if not accounts:
            st.info("Add a bank account before entering transactions.")
            return

        account_map = {row["id"]: row for row in accounts}

        st.markdown("#### Record Bank Transaction")
        with st.form("bank-transaction-form", clear_on_submit=True):
            bank_account_id = st.selectbox(
                "Bank Account",
                options=list(account_map.keys()),
                format_func=lambda item_id: _bank_account_option_label(account_map[item_id]),
            )
            transaction_date = st.date_input("Transaction Date", value=date.today())
            amount = st.number_input("Amount", value=100.0, step=25.0, format="%.2f")
            description = st.text_input("Description")
            reference_code = st.text_input("Reference Code")

            save = st.form_submit_button("Add Bank Transaction", use_container_width=True)
            if save:
                try:
                    STORE.add_bank_transaction(
                        bank_account_id=bank_account_id,
                        transaction_date=transaction_date,
                        description=description,
                        amount_cents=cents_from_amount(float(amount)),
                        reference_code=reference_code,
                    )
                    st.success("Bank transaction saved.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

        st.markdown("##### CSV Import")
        uploaded_file = st.file_uploader(
            "Import bank transactions",
            type=["csv"],
            help="CSV columns: transaction_date, description, amount, reference_code (optional)",
        )
        import_account_id = st.selectbox(
            "Import Into Bank Account",
            options=list(account_map.keys()),
            format_func=lambda item_id: _bank_account_option_label(account_map[item_id]),
            key="bank-import-account",
        )

        if uploaded_file is not None:
            try:
                import_df = pd.read_csv(uploaded_file)
                required = {"transaction_date", "description", "amount"}
                missing = required - set(import_df.columns)
                if missing:
                    st.error(
                        "CSV is missing required columns: " + ", ".join(sorted(missing))
                    )
                else:
                    st.dataframe(import_df.head(10), use_container_width=True, hide_index=True)
                    if st.button("Import Transactions", use_container_width=True):
                        imported = 0
                        for _, row in import_df.iterrows():
                            if pd.isna(row["transaction_date"]) or pd.isna(row["description"]) or pd.isna(row["amount"]):
                                continue

                            parsed_date = pd.to_datetime(row["transaction_date"]).date()
                            reference = None
                            if "reference_code" in import_df.columns and not pd.isna(row["reference_code"]):
                                reference = str(row["reference_code"])

                            STORE.add_bank_transaction(
                                bank_account_id=import_account_id,
                                transaction_date=parsed_date,
                                description=str(row["description"]),
                                amount_cents=cents_from_amount(float(row["amount"])),
                                reference_code=reference,
                            )
                            imported += 1

                        st.success(f"Imported {imported} transactions.")
                        st.rerun()
            except Exception as exc:
                st.error(f"Could not read CSV: {exc}")

    st.markdown("#### Monthly Reconciliation")
    accounts = _rows_to_dicts(STORE.list_bank_accounts(active_only=True))
    if not accounts:
        return

    account_map = {row["id"]: row for row in accounts}
    recon_controls = st.columns([1.1, 1.1, 0.8])
    with recon_controls[0]:
        recon_account_id = st.selectbox(
            "Bank Account",
            options=list(account_map.keys()),
            format_func=lambda item_id: _bank_account_option_label(account_map[item_id]),
            key="recon-account-id",
        )
    with recon_controls[1]:
        recon_month = st.date_input(
            "Month",
            value=date.today().replace(day=1),
            key="recon-month-anchor",
        )
    with recon_controls[2]:
        if st.button("Auto-match by reference", use_container_width=True):
            bounds = month_bounds(recon_month)
            matched = STORE.auto_match_by_reference(
                bank_account_id=recon_account_id,
                month_start=bounds.start,
                month_end=bounds.end,
            )
            if matched:
                st.success(f"Auto-matched {matched} donation(s).")
            else:
                st.info("No exact reference+amount matches found.")
            st.rerun()

    bounds = month_bounds(recon_month)
    snapshot = STORE.reconciliation_snapshot(
        bank_account_id=recon_account_id,
        month_start=bounds.start,
        month_end=bounds.end,
    )

    metric_cols = st.columns(4)
    with metric_cols[0]:
        st.metric("Donations Total", format_currency(int(snapshot["donation_total_cents"])))
    with metric_cols[1]:
        st.metric("Bank Total", format_currency(int(snapshot["bank_total_cents"])))
    with metric_cols[2]:
        st.metric("Variance", format_currency(int(snapshot["variance_cents"])))
    with metric_cols[3]:
        st.metric("Completion", f"{snapshot['completion_percent']}%")
    st.progress(min(max(float(snapshot["completion_percent"]) / 100, 0.0), 1.0))

    missing_bank = _rows_to_dicts(
        STORE.donations_missing_bank_match(
            bank_account_id=recon_account_id,
            month_start=bounds.start,
            month_end=bounds.end,
        )
    )
    missing_ledger = _rows_to_dicts(
        STORE.donations_missing_ledger_link(
            bank_account_id=recon_account_id,
            month_start=bounds.start,
            month_end=bounds.end,
        )
    )
    unmatched_transactions = _rows_to_dicts(
        STORE.unmatched_bank_transactions(
            bank_account_id=recon_account_id,
            month_start=bounds.start,
            month_end=bounds.end,
        )
    )

    recon_left, recon_right = st.columns(2, gap="large")
    with recon_left:
        st.markdown("##### Donations Missing Bank Match")
        missing_bank_df = pd.DataFrame(
            [
                {
                    "ID": row["id"],
                    "Date": row["donation_date"],
                    "Donor": donor_display_name(row),
                    "Amount": format_currency(int(row["amount_cents"])),
                    "Reference": row.get("reference_code") or "-",
                }
                for row in missing_bank
            ]
        )
        _table_or_info(missing_bank_df, "No donations are waiting for bank matching.")

        st.markdown("##### Donations Missing Ledger Link")
        missing_ledger_df = pd.DataFrame(
            [
                {
                    "ID": row["id"],
                    "Date": row["donation_date"],
                    "Donor": donor_display_name(row),
                    "Amount": format_currency(int(row["amount_cents"])),
                    "Reference": row.get("reference_code") or "-",
                }
                for row in missing_ledger
            ]
        )
        _table_or_info(missing_ledger_df, "All donations are linked to ledger entries.")

    with recon_right:
        st.markdown("##### Unmatched Bank Transactions")
        unmatched_bank_df = pd.DataFrame(
            [
                {
                    "ID": row["id"],
                    "Date": row["transaction_date"],
                    "Description": row["description"],
                    "Amount": format_currency(int(row["amount_cents"])),
                    "Reference": row.get("reference_code") or "-",
                }
                for row in unmatched_transactions
            ]
        )
        _table_or_info(unmatched_bank_df, "No unmatched bank transactions for this month.")

    if missing_bank and unmatched_transactions:
        st.markdown("##### Manual Match")
        donation_map = {row["id"]: row for row in missing_bank}
        transaction_map = {row["id"]: row for row in unmatched_transactions}

        match_cols = st.columns([1.1, 1.1, 1.2, 0.8])
        with match_cols[0]:
            donation_choice = st.selectbox(
                "Donation",
                options=list(donation_map.keys()),
                format_func=lambda item_id: (
                    f"#{item_id} {format_currency(int(donation_map[item_id]['amount_cents']))} "
                    f"{donor_display_name(donation_map[item_id])}"
                ),
                key="manual-match-donation",
            )

        selected_donation = donation_map[donation_choice]
        amount_matched_tx = [
            row
            for row in unmatched_transactions
            if row["amount_cents"] == selected_donation["amount_cents"]
        ]
        candidate_tx = amount_matched_tx or unmatched_transactions

        with match_cols[1]:
            tx_choice = st.selectbox(
                "Bank Transaction",
                options=[row["id"] for row in candidate_tx],
                format_func=lambda item_id: _bank_tx_option_label(transaction_map[item_id]),
                key="manual-match-bank-tx",
            )

        optional_ledger_entries = _rows_to_dicts(STORE.list_ledger_entries(unlinked_only=True))
        optional_ledger_map = {row["id"]: row for row in optional_ledger_entries}
        amount_matched_ledger = [
            row
            for row in optional_ledger_entries
            if row["amount_cents"] == selected_donation["amount_cents"]
        ]
        ledger_candidates = amount_matched_ledger or optional_ledger_entries

        with match_cols[2]:
            ledger_choice = st.selectbox(
                "Optional Ledger Link",
                options=[None] + [row["id"] for row in ledger_candidates],
                format_func=lambda item_id: (
                    "Keep Existing"
                    if item_id is None
                    else _ledger_option_label(optional_ledger_map[item_id])
                ),
                key="manual-match-ledger",
            )

        with match_cols[3]:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Match", use_container_width=True):
                try:
                    STORE.match_donation_to_bank_transaction(
                        donation_id=donation_choice,
                        bank_transaction_id=tx_choice,
                    )
                    if ledger_choice is not None:
                        STORE.link_donation_to_ledger(donation_choice, ledger_choice)
                        STORE.link_bank_transaction_to_ledger(tx_choice, ledger_choice)
                    st.success("Records matched.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))


def render_hipaa_review_tab() -> None:
    st.markdown("### HIPAA Sensitive Data Review")
    st.markdown(
        "<p class='section-note'>AI-assisted scan across all CRM objects to flag potential HIPAA-sensitive content for compliance review.</p>",
        unsafe_allow_html=True,
    )
    st.caption(
        "This scanner is a review aid. Final HIPAA determinations still require policy, legal, and compliance validation."
    )

    if "hipaa_scan_has_run" not in st.session_state:
        st.session_state.hipaa_scan_has_run = False
    if "hipaa_scan_findings" not in st.session_state:
        st.session_state.hipaa_scan_findings = []
    if "hipaa_scan_record_count" not in st.session_state:
        st.session_state.hipaa_scan_record_count = 0
    if "hipaa_scan_timestamp" not in st.session_state:
        st.session_state.hipaa_scan_timestamp = ""

    actions = st.columns([1, 1, 3], gap="small")
    with actions[0]:
        run_scan = st.button("Run AI Scan", use_container_width=True, key="hipaa-scan-run")
    with actions[1]:
        clear_results = st.button("Clear", use_container_width=True, key="hipaa-scan-clear")

    if clear_results:
        st.session_state.hipaa_scan_has_run = False
        st.session_state.hipaa_scan_findings = []
        st.session_state.hipaa_scan_record_count = 0
        st.session_state.hipaa_scan_timestamp = ""

    if run_scan:
        with st.spinner("Scanning CRM records for potential HIPAA-sensitive content..."):
            records = STORE.records_for_hipaa_scan()
            findings = HIPAA_SCANNER.scan_records(records)

        st.session_state.hipaa_scan_has_run = True
        st.session_state.hipaa_scan_findings = findings
        st.session_state.hipaa_scan_record_count = len(records)
        st.session_state.hipaa_scan_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        st.success(f"Scan complete. Found {len(findings)} potential issue(s).")

    if not st.session_state.hipaa_scan_has_run:
        st.info("Run AI Scan to analyze all records in Accounts, Opportunities, Engagements, Campaigns, and Finance objects.")
        return

    findings = st.session_state.hipaa_scan_findings
    record_count = int(st.session_state.hipaa_scan_record_count)
    scanned_at = st.session_state.hipaa_scan_timestamp

    if scanned_at:
        st.caption(f"Last scan: {scanned_at} | Records scanned: {record_count}")

    high_count = sum(1 for row in findings if row["severity"] == "High")
    medium_count = sum(1 for row in findings if row["severity"] == "Medium")
    low_count = sum(1 for row in findings if row["severity"] == "Low")
    unique_records = len({(row["table_name"], row["record_id"]) for row in findings})

    metrics = st.columns(5)
    with metrics[0]:
        st.metric("Potential Flags", str(len(findings)))
    with metrics[1]:
        st.metric("High", str(high_count))
    with metrics[2]:
        st.metric("Medium", str(medium_count))
    with metrics[3]:
        st.metric("Low", str(low_count))
    with metrics[4]:
        st.metric("Records Impacted", str(unique_records))

    if not findings:
        st.success("No potential HIPAA-sensitive findings were detected in this scan.")
        return

    filters = st.columns([1.2, 1.5, 2], gap="small")
    with filters[0]:
        selected_severity = st.multiselect(
            "Severity",
            options=["High", "Medium", "Low"],
            default=["High", "Medium", "Low"],
            key="hipaa-severity-filter",
        )
    with filters[1]:
        object_options = sorted({str(row["object_name"]) for row in findings})
        selected_objects = st.multiselect(
            "Object",
            options=object_options,
            default=object_options,
            key="hipaa-object-filter",
        )
    with filters[2]:
        keyword_filter = st.text_input(
            "Keyword Filter",
            placeholder="signal, field, context, or reason",
            key="hipaa-keyword-filter",
        ).strip().lower()

    filtered_findings: list[dict] = []
    for row in findings:
        if selected_severity and row["severity"] not in selected_severity:
            continue
        if selected_objects and row["object_name"] not in selected_objects:
            continue

        if keyword_filter:
            haystack = " ".join(
                [
                    str(row.get("signal") or ""),
                    str(row.get("field_name") or ""),
                    str(row.get("context") or ""),
                    str(row.get("reason") or ""),
                    str(row.get("object_name") or ""),
                ]
            ).lower()
            if keyword_filter not in haystack:
                continue

        filtered_findings.append(row)

    severity_order = {"High": 0, "Medium": 1, "Low": 2}
    filtered_findings.sort(
        key=lambda row: (
            severity_order.get(str(row["severity"]), 99),
            -int(row["confidence"]),
            str(row["object_name"]),
            int(row["record_id"]),
        )
    )

    findings_df = pd.DataFrame(
        [
            {
                "Severity": row["severity"],
                "Object": row["object_name"],
                "Record ID": row["record_id"],
                "Field": row["field_name"],
                "Signal": row["signal"],
                "Confidence": row["confidence"],
                "Matched Value": row["matched_text"],
                "Context": row["context"],
                "Why Flagged": row["reason"],
            }
            for row in filtered_findings
        ]
    )
    _table_or_info(findings_df, "No findings match the selected filters.")

    if not findings_df.empty:
        csv_data = findings_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Findings CSV",
            data=csv_data,
            file_name="hipaa_sensitive_data_findings.csv",
            mime="text/csv",
            use_container_width=False,
            key="hipaa-findings-download",
        )


def main() -> None:
    st.set_page_config(
        page_title="Harborlight Nonprofit Cloud",
        page_icon=":handshake:",
        layout="wide",
    )
    STORE.init_db()
    _inject_styles()
    _hero()

    tabs = st.tabs(
        [
            "Home",
            "Accounts & Contacts",
            "Engagement Plans",
            "Opportunities",
            "Campaigns",
            "Gift Entry & Ledger",
            "Reconciliation",
            "HIPAA Review",
        ]
    )

    with tabs[0]:
        render_dashboard()
    with tabs[1]:
        render_donors_tab()
    with tabs[2]:
        render_engagements_tab()
    with tabs[3]:
        render_donations_tab()
    with tabs[4]:
        render_campaigns_tab()
    with tabs[5]:
        render_ledger_tab()
    with tabs[6]:
        render_reconciliation_tab()
    with tabs[7]:
        render_hipaa_review_tab()


if __name__ == "__main__":
    main()
