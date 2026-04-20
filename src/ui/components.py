import streamlit as st


def require_auth(username: str, password: str) -> bool:
    """Shared basic auth. Returns True when logged in; blocks rendering otherwise."""
    if st.session_state.get("authed"):
        return True

    st.title("Bynder Image Tool")
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        submit = st.form_submit_button("Log in")
    if submit:
        if u == username and p == password:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Invalid credentials")
    return False
