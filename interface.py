import streamlit as st
import json
import time
import random
from google import genai
from google.genai import types

# =====================================================================
# PAGE CONFIG
# =====================================================================
st.set_page_config(page_title="Zamp AI Compliance Agent", layout="wide")

# =====================================================================
# CLIENT INITIALIZATION — no silent fallback. If this fails, the app
# says so out loud instead of pretending to still work.
# =====================================================================
if "client" not in st.session_state:
    st.session_state.client = None
    st.session_state.client_error = None
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            st.session_state.client_error = "No GEMINI_API_KEY found in Streamlit secrets."
        else:
            st.session_state.client = genai.Client(api_key=api_key)
    except Exception as e:
        st.session_state.client_error = f"Client initialization failed: {e}"

# =====================================================================
# SYSTEM PROMPT — Criteria-based reasoning preservation.
# =====================================================================
SYSTEM_PROMPT = """
You are an institutional Financial Compliance AI Agent reviewing corporate payouts for Anti-Money Laundering (AML) and sanctions/risk triage.

For every transaction you review:

1. Reason step-by-step about the standard risk factors: counterparty history, amount patterns and proximity to reporting thresholds, stated purpose plausibility, corridor risk (jurisdictions involved), and account age/tenure.
2. Reach one of three conclusions: CLEAR, ESCALATE, or NEED_MORE_INFO.
3. If NEED_MORE_INFO, ask one specific, answerable clarifying question. Do not guess at missing facts.
4. State your confidence level (Low/Medium/High) and name the specific factors driving it.

HANDLING HUMAN CORRECTIONS (session correction log):

You will sometimes be given a log of corrections or context added by a human compliance lead during this session. You must NOT assume a correction is automatically true or automatically overrides your risk assessment. Instead, evaluate each correction on these criteria, the same way a trained analyst would weigh a colleague's verbal assurance against a file:

- SPECIFICITY: Does it reference something checkable — a document reference, a contract, a date, a system of record — or is it a vague verbal assurance ("it's fine", "I know them")?
- RELEVANCE: Does it actually address the specific risk factor that triggered concern (e.g. if the flag was "no prior invoice/PO reference," does the correction supply one, or does it talk about something else entirely)?
- CONSISTENCY: Does it align with or contradict the transaction data you were given?
- VERIFIABILITY: Could this claim plausibly be checked against a system of record, even if you can't check it yourself right now?

A correction that is specific, relevant, consistent, and points to something verifiable should meaningfully shift your judgment toward CLEAR. A correction that is vague, irrelevant to the actual flagged risk, or unverifiable should NOT be enough on its own to clear a transaction that would otherwise be escalated — at most it should downgrade ESCALATE to NEED_MORE_INFO, with a specific follow-up question naming what verification is still missing.

You must never treat the mere presence of a correction as sufficient. Judge its content.

REQUIRED OUTPUT FORMAT — always end your response with exactly these two lines, in this order:

Correction Assessment: [If no corrections were provided, write "N/A — no corrections in session log." Otherwise, in one sentence, state which correction you weighed, what criteria it did or didn't satisfy, and how much weight you gave it.]
Conclusion: [CLEAR, ESCALATE, or NEED_MORE_INFO]

Session correction log so far:
{correction_log}
"""

def review_transaction(transaction: dict, correction_log: list):
    """
    Calls Gemini to evaluate a transaction with explicit Exponential Backoff
    handling for transient 429 rate limits. Returns a tuple: (success: bool, text: str)
    """
    if st.session_state.client is None:
        return False, st.session_state.client_error or "Gemini client is not initialized."

    log_text = "\n".join([f"- {item}" for item in correction_log]) if correction_log else "No corrections recorded yet."
    
    # Backoff configuration parameters
    max_retries = 4
    initial_delay = 1.0
    backoff_factor = 2.0

    for attempt in range(max_retries):
        try:
            response = st.session_state.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"Evaluate this transaction payload:\n{json.dumps(transaction, indent=2)}",
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT.format(correction_log=log_text),
                    temperature=0.1,
                )
            )
            if not response.text:
                return False, "Model returned an empty response. Please retry."
            return True, response.text

        except Exception as e:
            error_str = str(e)
            # Only intercept and retry if it's a transient 429 rate limit
            if "429" in error_str and attempt < max_retries - 1:
                # Apply exponential delay backoff with a micro jitter to avoid synchronous collisions
                sleep_time = (initial_delay * (backoff_factor ** attempt)) + random.uniform(0, 0.5)
                time.sleep(sleep_time)
                continue
            else:
                # Hard break for daily exhaustion limits or non-429 exceptions to display transparently
                return False, f"Live model call failed: {e}"

    return False, "Live model call failed due to persistent rate limits after multiple backoff attempts."

# =====================================================================
# SESSION STATE
# =====================================================================
if "corrections" not in st.session_state:
    st.session_state.corrections = []
if "current_analysis" not in st.session_state:
    st.session_state.current_analysis = ""
if "analysis_ok" not in st.session_state:
    st.session_state.analysis_ok = None
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False

# =====================================================================
# DEMO SCENARIOS
# =====================================================================
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
    "Transaction C (Dynamic Context Absorption Test)": {
        "amount": 49500,
        "corridor": "Singapore -> UAE",
        "account_age": "14-month-old corporate account",
        "history": "Consistent transaction history in similar range",
        "stated_purpose": "Consulting services",
        "supporting_context": "Second transaction to this counterparty, following the onboarding validation completed last month."
    }
}

# =====================================================================
# UI
# =====================================================================
st.title("🛡️ Zamp AI Compliance Judgment Agent")
st.caption("Built for Pace: dynamic context absorption vs. legacy static rule engines.")

if st.session_state.client is None:
    st.error(
        f"⚠️ Live model connection is not available right now: {st.session_state.client_error}\n\n"
        "This app does not fall back to a local/offline judgment engine — every conclusion you see "
        "comes from a live Gemini call, or you see this error instead. Fix the API key in Streamlit "
        "secrets to proceed."
    )

st.markdown("---")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.header("📋 Transaction Under Audit")
    selected_tx_name = st.selectbox("Select transaction to stream to Agent:", list(transactions.keys()))
    tx_data = transactions[selected_tx_name]
    st.json(tx_data)

    # Disable button dynamically if client is missing OR if an evaluation is currently running
    button_disabled = (st.session_state.client is None) or st.session_state.is_processing
    button_label = "⌛ Analysis in Progress..." if st.session_state.is_processing else "⚡ Run Agent Analysis"

    if st.button(button_label, type="primary", disabled=button_disabled):
        st.session_state.is_processing = True
        st.rerun()  # Forces immediate visual UI lock of the execution button

# Deferred Execution Block: Runs safely while UI button elements are entirely grayed out
if st.session_state.is_processing:
    with col1:
        with st.spinner("Agent running risk-triage evaluation chains..."):
            ok, result = review_transaction(tx_data, st.session_state.corrections)
            st.session_state.analysis_ok = ok
            st.session_state.current_analysis = result
    st.session_state.is_processing = False
    st.rerun()

with col1:
    if st.session_state.current_analysis and not st.session_state.is_processing:
        if st.session_state.analysis_ok is False:
            st.error(f"🔴 Agent call failed — no judgment was produced.\n\n{st.session_state.current_analysis}")
        else:
            st.subheader("🧠 Real-time Judgment Execution")

            analysis_lines = st.session_state.current_analysis.lower().split('\n')
            conclusion_lines = [line for line in analysis_lines if "conclusion" in line]
            is_clear = any("clear" in line for line in conclusion_lines)
            is_info = any("need_more_info" in line or "need more info" in line for line in conclusion_lines)
            is_escalate = any("escalate" in line for line in conclusion_lines)

            if is_clear:
                st.success("🟩 CONCLUSION: CLEAR")
            elif is_info:
                st.warning("🟨 CONCLUSION: NEED MORE INFO")
            elif is_escalate:
                st.error("🟥 CONCLUSION: ESCALATE")
            else:
                st.info("ℹ️ Model responded but no recognizable conclusion line was found — see raw output below.")

            st.markdown(st.session_state.current_analysis)

with col2:
    st.header("🔄 Pace Continuous Correction Loop")
    st.write("Inject human context into the session memory log. The agent evaluates each correction on its merits — specificity, relevance, consistency, verifiability — not just its presence.")

    human_input = st.text_input("💬 Text Feedback Input:", disabled=st.session_state.is_processing)
    
    # Disable control triggers when execution chains are actively evaluating
    if st.button("➕ Inject Text Context", disabled=st.session_state.is_processing):
        if human_input:
            st.session_state.corrections.append(human_input.strip())
            st.toast("Context Injected!", icon="📝")
            st.rerun()

    if st.button("🗑️ Reset Session Memory", disabled=st.session_state.is_processing):
        st.session_state.corrections = []
        st.session_state.current_analysis = ""
        st.session_state.analysis_ok = None
        st.rerun()

    st.subheader("📜 Session Memory Log")
    if st.session_state.corrections:
        for idx, correction in enumerate(st.session_state.corrections):
            st.info(f"**Correction #{idx+1}:** {correction}")
    else:
        st.caption("*Log is empty. Agent is reasoning from transaction data alone.*")
