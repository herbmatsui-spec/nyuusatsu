import streamlit as st
from pathlib import Path

def inject_custom_css(css_filename: str = "streamlit_theme.css") -> None:
    """static/css/ 配下のCSSを読み込み Streamlit に注入する。"""
    css_path = Path("static/css") / css_filename
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(f"<h1 class='lp-title'>{title}</h1>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<p class='lp-subtitle'>{subtitle}</p>", unsafe_allow_html=True)
