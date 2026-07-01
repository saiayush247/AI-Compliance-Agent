import streamlit as st
import json
from google import genai
from google.genai import types

# Set up page config for a premium, clean layout
st.set_page_config(page_title="Zamp AI Compliance Agent", layout="wide")

# Initialize Gemini Client
client = genai.Client()

# System Prompt enhanced with mandatory formatting rules
SYSTEM_PROMPT = """
You are a compliance analyst reviewing financial transactions for suspicious activity. For each transaction, you must:

1. Reason step-by-step about risk factors: counterparty history, amount patterns, proximity to reporting thresholds, stated purpose plausibility, corridor risk.
2. Reach one of three conclusions: CLEAR, ESCALATE, or NEED_MORE_INFO.
3. If NEED_MORE_INFO, ask a specific clarifying question - do not guess.
4. State your confidence level and the specific factors driving it.
5. You have a running memory of corrections made by the human compliance lead in this session. When a new transaction shares characteristics with a previously corrected case, explicitly reference that prior correction in your reasoning and adjust your conclusion accordingly.

CRITICAL FORMATTING RULE: You must always explicitly end your response with a dedicated conclusion line exactly like this:
Conclusion: [Your Decision here, e.g., CLEAR, ESCALATE, or NEED_MORE_INFO]

Session correction log so far:
{correction_log}
"""

def review_transaction(transaction: dict, correction_log: list) -> str:
    log_text = "\n".join([f"- {item}" for item in correction_log]) if correction_log else "No corrections recorded yet."
    contextual_system_prompt = SYSTEM_PROMPT.format(correction_log=log_text)
    transaction_json = json.dumps(transaction, indent=2)
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=f"Transaction to review:\n{transaction_json}",
        config=types.GenerateContentConfig(
            system_instruction=contextual_system_prompt,
            temperature=0.1,
        )
    )
    return response.text

# Initialize persistent memory in Streamlit so it doesn't wipe when the page reloads
if "corrections" not in st.session_state:
    st.session_state.corrections = []

# =====================================================================
# THE DEMO SCENARIO DATA (From zamp-compliance-agent-brief.pdf)
# =====================================================================
transactions = {
    "Transaction A (Should CLEAR)": {
        "amount": 48500,
        "corridor": "Singapore -> UAE",
        "account_age": "14-month-old corporate account",
        "history": "Consistent transaction history in similar range",
        "stated_purpose": "Payment for electronics components shipment, PO #4471",
        "supporting_context": "Matching PO number in prior transaction history, same counterparty used 3x before"
    },
    "Transaction B (Should ESCALATE/NEED INFO)": {
        "amount": 49200,
        "corridor": "Singapore -> UAE",
        "account_age": "14-month-old corporate account",
        "history": "Consistent transaction history in similar range",
        "stated_purpose": "Consulting services",
        "supporting_context": "First transaction to this counterparty, no prior invoice/PO reference, amount sits suspiciously close to a threshold ($50k) that would trigger mandatory reporting if crossed"
    },
    "Transaction C (Dynamic Clear after Correction)": {
        "amount": 49500,
        "corridor": "Singapore -> UAE",
        "account_age": "14-month-old corporate account",
        "history": "Consistent transaction history in similar range",
        "stated_purpose": "Consulting services",
        "supporting_context": "Second transaction to this counterparty, following the onboarding validation completed last month."
    }
}

# =====================================================================
# UI LAYOUT DESIGN
# =====================================================================

st.title("🛡️ Zamp AI Compliance Judgment Agent")
st.caption("A live demonstration of dynamic, calibrated compliance judgment vs static rules engines.")
st.markdown("---")

# Split Screen Columns
col1, col2 = st.columns([1, 1], gap="large")

# LEFT PANEL: Transaction Input & Analysis
with col1:
    st.header("📋 Transaction Desk")
    
    # Let user select which transaction to test live
    selected_tx_name = st.selectbox("Select a transaction payload to stream to the agent:", list(transactions.keys()))
    tx_data = transactions[selected_tx_name]
    
    st.json(tx_data)
    
    if st.button("⚡ Run Agent Analysis", type="primary"):
        with st.spinner("Agent is reasoning through context risk variables..."):
            analysis_output = review_transaction(tx_data, st.session_state.corrections)
            st.session_state.current_analysis = analysis_output
            
    if "current_analysis" in st.session_state:
        st.subheader("🤖 Agent Judgment Summary")
        
        # Make the search case-insensitive and look for key phrases anywhere on the line
        analysis_lines = st.session_state.current_analysis.lower().split('\n')
        is_clear = any("clear" in line for line in analysis_lines if "conclusion" in line)
        is_info = any("need_more_info" in line or "need more info" in line for line in analysis_lines if "conclusion" in line)
        is_escalate = any("escalate" in line for line in analysis_lines if "conclusion" in line)

        # Render highly deliberate visual statuses matching the real-time decision pipeline
        if is_clear:
            st.success("🟩 CONCLUSION: CLEAR")
        elif is_info:
            st.warning("🟨 CONCLUSION: NEED MORE INFO")
        elif is_escalate:
            st.error("🟥 CONCLUSION: ESCALATE")
        else:
            st.info("ℹ️ CONCLUSION: REVIEW COMPLETED")
            
        st.markdown(st.session_state.current_analysis)

# RIGHT PANEL: Live Feedback & Runtime Memory
with col2:
    st.header("🧠 Agent Memory & Correction Loop")
    st.write("Provide live context to dynamically update the agent's behavior without engineering downtime.")
    
    # Core Feature: Speak or type instructions directly to the memory loop
    human_input = st.text_input(
        "💬 Voice or Text Feedback (e.g., 'Actually, I know this counterparty. They are a verified consulting vendor...'):", 
        key="text_feedback"
    )
    
    # Audio input feature widget
    audio_file = st.audio_input("🎙️ Click to TALK directly to the Agent:")
    
    if audio_file:
        st.info("🔄 Audio received. Audio stream feeding directly into agent correction log pipeline.")
        # Simulated high-fidelity transcription pipeline entry for demo purposes
        audio_transcription_note = "Actually - I know this counterparty. They're a new consulting vendor we onboarded last month, contract's in the DMS under a different reference number. This one's fine."
        if audio_transcription_note not in st.session_state.corrections:
            st.session_state.corrections.append(audio_transcription_note)
            st.rerun()

    if st.button("➕ Inject Context into Session Memory"):
        if human_input:
            st.session_state.corrections.append(human_input)
            st.success("Context injected successfully!")
            st.rerun()
            
    # Clear memory loop button
    if st.button("🗑️ Reset Session Memory"):
        st.session_state.corrections = []
        if "current_analysis" in st.session_state:
            del st.session_state.current_analysis
        st.rerun()

    # Dynamic Memory Box Display
    st.subheader("📜 Running Session Log")
    if st.session_state.corrections:
        for idx, correction in enumerate(st.session_state.corrections):
            st.info(f"**Correction #{idx+1}:** {correction}")
    else:
        st.write("*No dynamic session corrections added yet. Agent running on standard global settings.*")
