import copy
import streamlit as st

KEY = "hardware_demo_records"
def load():
    if KEY not in st.session_state:
        st.session_state[KEY] = {"model": None, "models": [], "samples": []}
    return copy.deepcopy(st.session_state[KEY])

def save(data):
    st.session_state[KEY] = copy.deepcopy(data)
