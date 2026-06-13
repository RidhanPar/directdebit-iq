"""Streamlit evidence page for the score-to-action automation path."""

import streamlit as st

from app.action_api_client import action_api_health


def page_action_automation() -> None:
    st.markdown("## Auditable Retry Automation")
    st.caption("Model score to human approval to idempotent operational action.")

    api_status, api_url = action_api_health()

    cols = st.columns(4)
    cols[0].metric("Action API", api_status)
    cols[1].metric("Decision Gate", "Human approval")
    cols[2].metric("Execution Safety", "Idempotent")
    cols[3].metric("Evidence", "Audit + trace IDs")

    st.markdown(
        """
        ```mermaid
        flowchart LR
            P[Scheduled payment] --> S[Score payment]
            S --> A[Persist prediction audit]
            A --> R[Create retry recommendation]
            R --> H{Human approval}
            H -->|Approved| E[Execute idempotent retry]
            H -->|Rejected| X[Record rejection]
            E --> O[Persist action outcome]
        ```
        """
    )

    st.info(
        "Import `automation/n8n_retry_approval_workflow.json` into n8n to run this flow. "
        "The workflow cannot execute customer-impacting actions until a reviewer decision is persisted."
    )
    st.code(
        f"""POST {api_url}/predictions
Authorization: Bearer <operator-jwt>

POST {api_url}/actions/<action-id>/decision
Authorization: Bearer <reviewer-jwt>

POST {api_url}/actions/<action-id>/execute
Authorization: Bearer <operator-jwt>""",
        language="http",
    )
