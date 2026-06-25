#!/usr/bin/env python3
"""DAFO Explorer."""
import sqlite3, urllib.parse, html
from pathlib import Path
import streamlit as st
import pandas as pd

DB = Path.home() / "Projects/Analisis_Concursos_DAFO/concursos_dafo.db"
st.set_page_config(page_title="DAFO — Proyectos", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
#MainMenu, footer, header, [data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stSidebar"], .stAppDeployButton, div[data-testid="stDecoration"],
[data-testid="stStatusWidget"], [data-testid="stNotification"] { display: none !important; }
.stApp { background: #fff; }
.block-container { padding: 0 !important; max-width: 100% !important; }
section[data-testid="stVerticalBlock"] { gap: 0; }
.element-container { margin: 0 !important; padding: 0 !important; }
.row-widget.stHorizontal { gap: 1rem; flex-wrap: wrap; }
label, .st-emotion-cache-16idsys, .st-emotion-cache-1aej5mr { display: none !important; }
div[data-testid="stTextInput"] { margin: 0 !important; padding: 0 !important; }
div[data-testid="stTextInput"] > div { margin: 0 !important; padding: 0 !important; border: none !important; }
div[data-testid="stTextInput"] input {
    border: 1px solid #ccc !important; border-radius: 0 !important;
    padding: 0.5rem 0.7rem !important; font-size: 0.9rem !important;
    background: #fff !important; line-height: 1.4 !important;
    width: 100% !important; outline: none !important;
}
div[data-testid="stTextInput"] input:focus { border-color: #666 !important; }
div[data-testid="stSelectbox"] { margin: 0 !important; padding: 0 !important; }
div[data-testid="stSelectbox"] > div {
    border-radius: 0 !important; border: 1px solid #ccc !important;
    padding: 0.35rem 0.5rem !important; min-height: auto !important;
    background: #fff !important; box-shadow: none !important;
}
div[data-testid="stSelectbox"] > div:hover { border-color: #999 !important; }
div[data-testid="stMultiSelect"] { margin: 0 !important; }
div[data-testid="stMultiSelect"] > div {
    border-radius: 0 !important; border: 1px solid #ccc !important;
    min-height: auto !important; padding: 0.2rem !important;
}
div[data-testid="stCheckbox"] { margin: 0.5rem 0 !important; min-height: auto !important; }
div[data-testid="stCheckbox"] label {
    font-size: 0.82rem !important; color: #333 !important; gap: 0.4rem !important;
}
div[data-testid="stNumberInput"] { margin: 0 !important; }
div[data-testid="stNumberInput"] input {
    border-radius: 0 !important; border: 1px solid #ccc !important;
    padding: 0.35rem 0.5rem !important; font-size: 0.82rem !important;
}
div[data-testid="stExpander"] { border: none !important; margin: 0 !important; }
div[data-testid="stExpander"] > div:first-child { padding: 0 !important; }
div[data-testid="stExpander"] summary {
    font-size: 0.82rem !important; color: #888 !important;
    padding: 0.3rem 0 !important; min-height: auto !important;
}
div[data-testid="stExpander"] summary:hover { color: #333 !important; }
div[data-testid="stExpander"] summary svg { width: 12px !important; height: 12px !important; }
div[data-testid="stForm"] { border: none !important; padding: 0 !important; }
.css-1d391kg, .st-emotion-cache-1r6slb0 { padding: 0 !important; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_conn():
    return sqlite3.connect(str(DB), check_same_thread=False)

def query(sql, params=()):
    return pd.read_sql_query(sql, get_conn(), params=params)

ANIOS = sorted(query("SELECT anio FROM convocatoria ORDER BY anio")["anio"].tolist())
LINEAS = sorted(query("SELECT codigo FROM linea_concursable ORDER BY codigo")["codigo"].tolist())
MONTO_DB = query("SELECT SUM(monto_otorgado) FROM proyecto").iloc[0, 0]
TOTAL_DB = query("SELECT COUNT(*) FROM proyecto").iloc[0, 0]
MONTO_FMT = f"S/ {MONTO_DB:,.2f}"

for k in ["pg", "pp"]:
    if k not in st.session_state:
        st.session_state[k] = 25 if k == "pp" else 1

# ── NAV ───────────────────────────────────────────────────────────────
st.markdown("""
<div style="border-bottom:1px solid #eee;background:#fff;position:sticky;top:0;z-index:100">
<div style="max-width:1200px;margin:0 auto;padding:0 2rem;display:flex;align-items:center;justify-content:space-between;height:3.5rem">
    <div style="display:flex;align-items:center;gap:2.5rem">
        <span style="font-family:Georgia,serif;font-size:1.15rem;font-weight:700;color:#111;letter-spacing:0.3px">DAFO</span>
        <nav style="display:flex;gap:1.5rem;font-size:0.82rem">
            <a href="#" style="color:#111;text-decoration:none">Proyectos</a>
            <a href="#" style="color:#888;text-decoration:none">Dashboard</a>
            <a href="#" style="color:#888;text-decoration:none">Personas</a>
            <a href="#" style="color:#888;text-decoration:none">Resoluciones</a>
            <a href="#" style="color:#888;text-decoration:none">Documentos</a>
        </nav>
    </div>
    <div style="display:flex;align-items:center;gap:1rem;font-size:0.78rem;color:#888">
        <span>es</span>
    </div>
</div>
</div>
""", unsafe_allow_html=True)

# ── MAIN ──────────────────────────────────────────────────────────────
st.markdown('<div style="max-width:1200px;margin:0 auto;padding:0 2rem">', unsafe_allow_html=True)
st.markdown(f"""<h1 style="font-family:Georgia,serif;font-size:2rem;font-weight:700;color:#111;margin:2.5rem 0 0.25rem 0;letter-spacing:-0.3px">Proyectos</h1>
<p style="font-size:0.85rem;color:#888;margin:0 0 1.5rem 0">{TOTAL_DB:,} registros · {MONTO_FMT} otorgados · 2019–2025</p>""", unsafe_allow_html=True)

# ── SEARCH + FILTERS in a form ───────────────────────────────────────
with st.form("search_form", border=False):
    st.markdown("""
    <style>
    div[data-testid="stForm"] { border: none !important; padding: 0 !important; background: none !important; }
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<p style="font-size:0.82rem;color:#888;margin:0 0 0.3rem 0">Search for:</p>', unsafe_allow_html=True)
    search = st.text_input("", placeholder="Search", label_visibility="collapsed")
    st.markdown('<p style="font-size:0.82rem;color:#888;margin:1rem 0 0.4rem 0">Filter by edition</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        yf = st.selectbox("From", ANIOS, index=0, label_visibility="collapsed")
    with c2:
        yt = st.selectbox("To", ANIOS, index=len(ANIOS)-1, label_visibility="collapsed")
    st.markdown("""
    <style>
    div[data-testid="stCheckbox"] { margin: 0.5rem 0 !important; }
    </style>
    """, unsafe_allow_html=True)
    show_adv = st.checkbox("Advanced search", value=False)
    
    linea_filter = LINEAS
    monto_max = 500000
    tipo_per = "Todas"
    
    if show_adv:
        st.markdown('<div style="background:#fafafa;border:1px solid #eee;padding:1.25rem;margin:0.5rem 0 1rem 0"><p style="font-size:0.78rem;color:#888;margin:0 0 0.8rem 0;text-transform:uppercase;letter-spacing:0.5px">Advanced search</p>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown('<p style="font-size:0.78rem;color:#888;margin:0 0 0.3rem 0">Línea</p>', unsafe_allow_html=True)
            linea_filter = st.multiselect("", LINEAS, default=LINEAS, label_visibility="collapsed")
        with c2:
            st.markdown('<p style="font-size:0.78rem;color:#888;margin:0 0 0.3rem 0">Tipo persona</p>', unsafe_allow_html=True)
            tipo_per = st.selectbox("", ["Todas", "Natural", "Jurídica"], label_visibility="collapsed")
        with c3:
            st.markdown('<p style="font-size:0.78rem;color:#888;margin:0 0 0.3rem 0">Monto máx. (S/)</p>', unsafe_allow_html=True)
            monto_max = st.number_input("", value=500000, min_value=0, step=10000, label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.form_submit_button("Search", type="secondary", use_container_width=False)

# ── QUERY ─────────────────────────────────────────────────────────────
where = ["p.monto_otorgado <= ?"]
params = [monto_max]
if yf: params.append(int(yf)); where.append("cv.anio >= ?")
if yt: params.append(int(yt)); where.append("cv.anio <= ?")
if linea_filter:
    ph = ",".join("?" for _ in linea_filter)
    params.extend(linea_filter); where.append(f"lc.codigo IN ({ph})")
if show_adv and tipo_per and tipo_per != "Todas":
    where.append("pe.tipo = ?")
    params.append("natural" if tipo_per == "Natural" else "juridica")
if search:
    for w in search.split():
        l = f"%{w}%"
        where.append("(ob.titulo LIKE ? OR pe.nombres LIKE ? OR pe.apellidos LIKE ? OR r.numero LIKE ?)")
        params.extend([l, l, l, l])

total = query(f"""
    SELECT COUNT(*) FROM proyecto p
    JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
    JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
    JOIN convocatoria cv ON ca.convocatoria_id = cv.id
    LEFT JOIN obra ob ON p.obra_id = ob.id
    LEFT JOIN persona pe ON p.persona_beneficiaria_id = pe.id
    LEFT JOIN proyecto_resolucion rp ON p.id = rp.proyecto_id
    LEFT JOIN resolucion r ON rp.resolucion_id = r.id
    WHERE {' AND '.join(where)}
""", params).iloc[0, 0]

PER_PAGE = st.session_state.pp
total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
page = st.session_state.pg
if page > total_pages: page = 1
offset = (page - 1) * PER_PAGE

st.markdown(f'<p style="font-size:0.85rem;color:#888;margin:0.5rem 0 0 0"><strong style="color:#111">{total:,}</strong> result(s) found</p>', unsafe_allow_html=True)

df = query(f"""
    SELECT p.id, cv.anio, lc.codigo as linea, ob.titulo,
           pe.nombres, pe.apellidos, pe.tipo as tipo_per,
           p.monto_otorgado as monto, r.numero as rd
    FROM proyecto p
    JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
    JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
    JOIN convocatoria cv ON ca.convocatoria_id = cv.id
    LEFT JOIN obra ob ON p.obra_id = ob.id
    LEFT JOIN persona pe ON p.persona_beneficiaria_id = pe.id
    LEFT JOIN proyecto_resolucion rp ON p.id = rp.proyecto_id
    LEFT JOIN resolucion r ON rp.resolucion_id = r.id
    WHERE {' AND '.join(where)}
    ORDER BY cv.anio DESC, lc.codigo
    LIMIT ? OFFSET ?
""", params + [PER_PAGE, offset])

if df.empty:
    st.markdown('<p style="text-align:center;padding:3rem;color:#999">Sin resultados</p>', unsafe_allow_html=True)
else:
    for _, r in df.iterrows():
        nombre = html.escape(f"{r['nombres'] or ''} {r['apellidos'] or ''}".strip() or "—")
        titulo = html.escape(r["titulo"] or "—")
        monto_fmt = f"S/ {r['monto']:,.2f}" if r["monto"] else "—"
        rd = html.escape(r["rd"] or "—")
        tipo_label = "Persona natural" if r["tipo_per"] == "natural" else "Persona jurídica"

        st.markdown(f"""
        <div style="padding:1.1rem 0;border-bottom:1px solid #eee">
            <h3 style="font-family:Georgia,serif;font-size:1.05rem;font-weight:700;margin:0 0 0.2rem 0;line-height:1.3">
                <a href="#" style="color:#111;text-decoration:none">{titulo}</a>
            </h3>
            <p style="font-size:0.85rem;color:#888;margin:0.1rem 0">
                {nombre} · {monto_fmt} · RD {rd}
            </p>
            <p style="font-size:0.8rem;color:#aaa;margin:0.1rem 0">
                {r['linea']} · {int(r['anio'])} · {tipo_label}
            </p>
        </div>
        """, unsafe_allow_html=True)

        with st.expander(f"Open details for {titulo} [+]"):
            ints = query("""
                SELECT pe.nombres, pe.apellidos, pi.tipo
                FROM proyecto_integrante pi JOIN persona pe ON pi.persona_id = pe.id
                WHERE pi.proyecto_id = ?
            """, [r["id"]])
            if not ints.empty:
                for _, i in ints.iterrows():
                    st.markdown(f"- {i['nombres']} {i['apellidos']} ({i['tipo'] or '—'})")
            else:
                st.markdown("*Sin integrantes*")
            res = query("""
                SELECT r.numero, r.tipo FROM resolucion r
                JOIN proyecto_resolucion rp ON r.id = rp.resolucion_id
                WHERE rp.proyecto_id = ?
            """, [r["id"]])
            if not res.empty:
                st.markdown(f"**Resolución:** {res.iloc[0]['numero']} ({res.iloc[0]['tipo']})")

    # PAGINATION
    st.markdown("""
    <div style="display:flex;align-items:center;justify-content:space-between;padding:1.5rem 0;font-size:0.85rem">
    """, unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        pp = st.selectbox("", [15, 25, 50, 100], index=[15, 25, 50, 100].index(PER_PAGE), label_visibility="collapsed")
        if pp != PER_PAGE:
            st.session_state.pp = pp; st.session_state.pg = 1; st.rerun()
    with c2:
        st.markdown(f"<p style='text-align:center;color:#888'>Page {page} of {total_pages}</p>", unsafe_allow_html=True)
    with c3:
        jump = st.number_input("", min_value=1, max_value=total_pages, value=page, label_visibility="collapsed")
        if jump != page:
            st.session_state.pg = jump; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# FOOTER
st.markdown(f"""
<div style="background:#111;color:#888;margin-top:3rem;padding:2.5rem 0;font-size:0.82rem">
<div style="max-width:1200px;margin:0 auto;padding:0 2rem">
    <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:2.5rem">
        <div>
            <p style="font-family:Georgia,serif;color:#fff;font-size:1.1rem;font-weight:700;margin:0 0 0.5rem 0">DAFO</p>
            <p style="margin:0.2rem 0">Estímulos Económicos del Ministerio</p>
            <p style="margin:0.2rem 0">de Cultura del Perú</p>
            <p style="margin:0.2rem 0;color:#666">Solo lectura</p>
        </div>
        <div>
            <p style="color:#fff;font-weight:600;margin:0 0 0.5rem 0">Explore the website</p>
            <p style="margin:0.2rem 0">Proyectos · Dashboard</p>
            <p style="margin:0.2rem 0">Personas · Resoluciones · Documentos</p>
        </div>
        <div>
            <p style="color:#fff;font-weight:600;margin:0 0 0.5rem 0">Database</p>
            <p style="margin:0.2rem 0">{total:,} proyectos</p>
            <p style="margin:0.2rem 0">{MONTO_FMT} otorgados</p>
            <p style="margin:0.2rem 0">SQLite · 14 tablas</p>
        </div>
    </div>
    <p style="text-align:center;margin-top:2rem;border-top:1px solid #222;padding-top:1.2rem;font-size:0.75rem;color:#555">Powered by Streamlit · Datos DAFO</p>
</div>
</div>
""", unsafe_allow_html=True)
