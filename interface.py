import streamlit as st
import json
from google import genai
from google.genai import types

# 1. Premium UI Page Configuration
st.set_page_config(page_title="Zamp AI Compliance Agent", layout="wide")

# Initialize the Google GenAI Client
client = genai.Client()

# 2. Strategic Criteria-Based System Prompt (Fully Un-rigged)
SYSTEM_PROMPT = """
You are an institutional Financial Compliance AI Agent reviewing corporate payouts for Anti-Money Laundering (AML) and compliance risk-triage. 

For each transaction payload, your objective is to perform a rigorous evaluation based on two distinct layers:
1. BASELINE RISK PROFILE: Evaluate structural indicators such as transaction amount patterns, corridor jurisdictions (e.g., transit hubs), account maturity, and proximity to structural reporting limits (like the $50,000 regulatory reporting threshold).
2. DYNAMIC CORRECTION ANALYSIS: Review the 'Running Session Correction Log' containing historical or contextual feedback from human compliance leads. 

CRITICAL REASONING CORE:
Do not blindly accept human overrides. Instead, score the human input based on clear, objective criteria:
- HIGH WEIGHT (CREDIBLE): Input that provides explicit, verifiable corporate reference data. Look for system names (e.g., 'DMS', 'Salesforce', 'SAP'), concrete legal or operational milestones ('completed KYC audit last Tuesday'), specific internal routing tickets, or explicit contract locations.
- LOW WEIGHT (VAGUE): Input that relies on subjective, casual, or emotional assurances (e.g., 'This client is fine', 'Trust me', 'I personally know them'). Treat these as unverified and maintain a conservative stance.

If a high-weight human correction directly neutralizes the specific structural risk that caused suspicion (e.g., validating a missing contract for a payload near a threshold limit), you may dynamically downgrade the alert and CLEAR the transaction. Otherwise, hold or ESCALATE.

CRITICAL FORMATTING REQUIREMENT: Your final response must always conclude with an isolated, explicitly structured line exactly matching this format:
Conclusion: [CLEAR, ESCALATE, or NEED_MORE_INFO]

Running Session Correction Log:
{correction_log}
"""

def review_transaction(transaction: dict, correction_log: list) -> str:
    """Compiles context, handles communication with Gemini, and catches blips gracefully."""
    log_text = "\n".join([f"- {item}" for item in correction_log]) if correction_log else "No corrections recorded yet."
    contextual_system_prompt = SYSTEM_PROMPT.format(correction_log=log_text)
    transaction_json = json.dumps(transaction, indent=2)
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Evaluate this transaction payload against system criteria:\n{transaction_json}",
            config=types.GenerateContentConfig(
                system_instruction=contextual_system_prompt,
                temperature=0.1,
            )
        )
        return response.text
    except Exception as e:
        return f"Conclusion: NEED_MORE_INFO\n\n⚠️ Upstream Connection Blip: Rate limit hit or API adjustment needed. Please try re-running analysis."

# Initialize State
if "corrections" not in st.session_state:
    st.session_state.corrections = []
if "current_analysis" not in st.session_state:
    st.session_state.current_analysis = ""

# Scenarios
transactions = {
    "Transaction A (Standard Operating Baseline)": {
        "amount": 48500,
        "corridor": "Singapore -> UAE",
        "account_age": "14-month-old corporate account",
        "history": "Consistent transaction history in similar range",
        "stated_purpose": "Payment for electronics components shipment, PO #4471",
        "supporting_context": "Matching PO number in prior transaction history, same counterparty used 3x before"
    },
    "Transaction B (High Structuring Risk - No History)": {
        "amount": 49200,
        "corridor": "Singapore -> UAE",
        "account_age": "14-month-old corporate account",
        "history": "Consistent transaction history in similar range",
        "stated_purpose": "Consulting services",
        "supporting_context": "First transaction to this counterparty, no prior invoice/PO reference, amount sits suspiciously close to a threshold ($50k) that would trigger mandatory reporting if crossed"
    },
    "Transaction C (The Dynamic Context Absorption Test)": {
        "amount": 49500,
        "corridor": "Singapore -> UAE",
        "account_age": "14-month-old corporate account",
        "history": "Consistent transaction history in similar range",
        "stated_purpose": "Consulting services",
        "supporting_context": "Second transaction to this counterparty, following the onboarding validation completed last month."
    }
}

st.title("🛡️ Zamp AI Compliance Judgment Agent")
st.caption("Built for Pace: Dynamic Context Absorption vs. Legacy Static Rule Engines.")
st.markdown("---")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.header("📋 Transaction Under Audit")
    selected_tx_name = st.selectbox("Select transaction to stream to Agent:", list(transactions.keys()))
    tx_data = transactions[selected_tx_name]
    st.json(tx_data)

    if st.button("⚡ Run Agent Analysis", type="primary"):
        with st.spinner("Agent running risk-triage evaluation chains..."):
            analysis_output = review_transaction(tx_data, st.session_state.corrections)
            st.session_state.current_analysis = analysis_output

    if st.session_state.current_analysis:
        st.subheader("🧠 Real-time Judgment Execution")
        
        analysis_lines = st.session_state.current_analysis.lower().split('\n')
        is_clear = any("clear" in line for line in analysis_lines if "conclusion" in line)
        is_info = any("need_more_info" in line or "need more info" in line for line in analysis_lines if "conclusion" in line)
        is_escalate = any("escalate" in line for line in analysis_lines if "conclusion" in line)

        if is_clear:
            st.success("🟩 CONCLUSION: CLEAR")
        elif is_info:
            st.warning("🟨 CONCLUSION: NEED MORE INFO")
        elif is_escalate:
            st.error("🟥 CONCLUSION: ESCALATE")
            
        st.markdown(st.session_state.current_analysis)

with col2:
    st.header("🔄 Pace Continuous Correction Loop")
    st.write("Inject dynamic human context into the session memory log to realign the agent's reasoning.")

    human_input = st.text_input("💬 Text Feedback Input:")
    if st.button("➕ Inject Text Context"):
        if human_input:
            st.session_state.corrections.append(human_input.strip())
            st.toast("Context Injected!", icon="📝")
            st.rerun()

    if st.button("🗑️ Reset Session Memory"):
        st.session_state.corrections = []
        st.session_state.current_analysis = ""
        st.rerun()

    st.subheader("📜 Session Memory Log")
    if st.session_state.corrections:
        for idx, correction in enumerate(st.session_state.corrections):
            st.info(f"**Correction #{idx+1}:** {correction}")
    else:
        st.caption("*Log is completely empty. Agent processing exclusively via global regulations.*")
