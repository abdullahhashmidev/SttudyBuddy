"""
Universal Secrets Resolver
Priority: st.secrets (Streamlit Cloud) → .env (local) → default
Streamlit ke bahar bhi safe (import error nahi aayega).
"""

import os


def get_secret(key: str, default=None):
    """Works on Streamlit Cloud AND locally with .env"""
    # 1) Streamlit Cloud secrets try karo
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass  # Local run ya streamlit installed nahi

    # 2) .env fallback
    value = os.getenv(key, default)

    # 3) Quotes clean karo (agar .env mein quotes hain)
    if isinstance(value, str):
        value = value.strip().strip('"').strip("'")

    return value
