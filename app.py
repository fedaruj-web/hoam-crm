import streamlit as st

from database import authenticate_user, init_db
from ui.pages import (
    render_activities,
    render_clients,
    render_data_quality,
    render_dashboard,
    render_followups,
    render_import_export,
    render_leads,
    render_login,
    render_new_lead,
    render_opportunities,
    render_proposals,
    render_reports,
    render_users,
)
from services import allowed_menus
from ui.styles import apply_theme, render_sidebar_brand

st.set_page_config(page_title="Hoam Capital CRM", page_icon="H", layout="wide")
init_db()
apply_theme()

if "user" not in st.session_state:
    render_login(authenticate_user)
    st.stop()

current_user = st.session_state["user"]
render_sidebar_brand(current_user)

menu_items = allowed_menus(current_user)
if st.session_state.get("menu") not in menu_items:
    st.session_state["menu"] = menu_items[0]

NAV_GROUPS = {
    "Principal": ["Dashboard", "Leads", "Novo Lead"],
    "Relacionamento": ["Atividades", "Follow-ups", "Clientes"],
    "Pipeline": ["Oportunidades", "Propostas"],
    "Gestao": ["Relatorios", "Qualidade de Dados", "Importar/Exportar", "Usuarios"],
}

st.sidebar.markdown('<div class="hoam-sidebar-nav">', unsafe_allow_html=True)
for group, items in NAV_GROUPS.items():
    visible_items = [item for item in items if item in menu_items]
    if not visible_items:
        continue
    st.sidebar.markdown(f'<div class="hoam-nav-group">{group}</div>', unsafe_allow_html=True)
    for item in visible_items:
        if item == st.session_state["menu"]:
            st.sidebar.markdown(f'<div class="hoam-nav-active">{item}</div>', unsafe_allow_html=True)
        elif st.sidebar.button(item, key=f"nav_{item}", use_container_width=True):
            st.session_state["menu"] = item
            st.rerun()
st.sidebar.markdown("</div>", unsafe_allow_html=True)

st.sidebar.markdown('<div class="hoam-sidebar-footer">', unsafe_allow_html=True)
if st.sidebar.button("Sair", use_container_width=True):
    st.session_state.pop("user", None)
    st.session_state.pop("menu", None)
    st.rerun()
st.sidebar.markdown("</div>", unsafe_allow_html=True)

menu = st.session_state["menu"]

if menu == "Dashboard":
    render_dashboard()
elif menu == "Leads":
    render_leads(current_user)
elif menu == "Novo Lead":
    render_new_lead(current_user)
elif menu == "Atividades":
    render_activities(current_user)
elif menu == "Oportunidades":
    render_opportunities()
elif menu == "Propostas":
    render_proposals(current_user)
elif menu == "Follow-ups":
    render_followups()
elif menu == "Clientes":
    render_clients()
elif menu == "Relatorios":
    render_reports()
elif menu == "Qualidade de Dados":
    render_data_quality()
elif menu == "Importar/Exportar":
    render_import_export()
elif menu == "Usuarios":
    render_users()
