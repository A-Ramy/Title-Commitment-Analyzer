"""Title Agent (Total Cash Home Buyers): entry point.

    uv run streamlit run app.py
"""

import streamlit as st

from ui.auth import gate
from ui.brand import LOGO_MARK, inject
from ui.layout import setup_screen, sidebar, tab_capsule
from ui.state import ai_ready

st.set_page_config(page_title="Title Agent · Total Cash Home Buyers", page_icon=str(LOGO_MARK), layout="wide")
inject()
gate()  # public URL (one private app per Streamlit account): nothing below runs until the person is allowed in

DEAL = st.Page("views/deal.py", title="Deal", icon=":material/fact_check:", url_path="deal")
MAIN = [
    st.Page("views/analyze.py", title="Analyze", icon=":material/upload_file:", url_path="analyze", default=True),
    st.Page("views/deals.py", title="Deals", icon=":material/folder_open:", url_path="deals"),
    st.Page("views/training.py", title="Training", icon=":material/school:", url_path="training"),
    st.Page("views/knowledge.py", title="Knowledge", icon=":material/menu_book:", url_path="knowledge"),
]
SETTINGS = st.Page("views/settings.py", title="Settings", icon=":material/tune:", url_path="settings")
page = st.navigation([*MAIN, DEAL, SETTINGS], position="hidden")

if not ai_ready():
    setup_screen()
    st.stop()

sidebar([MAIN[3], SETTINGS], DEAL)
tab_capsule(MAIN)
page.run()
