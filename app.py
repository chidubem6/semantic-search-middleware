import httpx
import streamlit as st

st.set_page_config(page_title="Semantic Search", page_icon="🔎")
st.title("Semantic Search Middleware")
question = st.chat_input("Ask a question about the indexed database")

if question:
    with st.chat_message("user"):
        st.write(question)
    try:
        response = httpx.post(
            "http://localhost:8000/api/v1/chat",
            json={"message": question},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        with st.chat_message("assistant"):
            st.write(payload["answer"])
            if payload["citations"]:
                st.caption(f"Sources: {payload['citations']}")
    except httpx.HTTPError as exc:
        st.error(f"API request failed: {exc}")
