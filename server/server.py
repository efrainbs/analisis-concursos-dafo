#!/usr/bin/env python3
"""DAFO Explorer — Flask server with FTS5 search and dynamic facets."""
import sqlite3, html, urllib.parse, re, unicodedata, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flask import Flask, render_template, request, jsonify
from dafo_common import REGIONS, resolve_region

def _strip_accents(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")

# Canonical region name per accent-stripped key (prefers accented form)
REGION_CANON = {}
for r in REGIONS:
    key = _strip_accents(r.upper())
    if key not in REGION_CANON:
        REGION_CANON[key] = r.upper()

DB = Path.home() / "Projects/Analisis_Concursos_DAFO/concursos_dafo"
DB = DB.with_suffix(".db")
REGIONS_CANONICAL = sorted(set(r.upper() for r in REGIONS if len(r) >= 3))
OBRA_TIPO_LABELS = {
    "audiovisual": "Obra audiovisual", "investigacion": "Investigación",
    "formacion": "Formación", "exhibicion": "Exhibición",
    "preservacion": "Preservación", "promocion": "Promoción",
    "gestion": "Gestión", "trayectoria": "Trayectoria",
}
app = Flask(__name__, template_folder="../templates")
app.config["TEMPLATES_AUTO_RELOAD"] = True


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

# bm25 weights for proyecto_fts columns (in FTS5 column order):
#   proyecto_id, titulo, descripcion, nombres, apellidos,
#   razon_social, region, linea_codigo, linea_nombre, modalidad,
#   integrantes, rd_numero, monto_str
# Higher weight = column matches count more (lower bm25 = more relevant).
BM25_WEIGHTS = "1, 10, 1, 4, 4, 5, 1, 8, 6, 3, 1, 6, 0.5"

# Common JOINs needed by every query (FTS subquery + main schema).
BASE_FROM = """
FROM proyecto p
{fts}
JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
JOIN convocatoria cv ON ca.convocatoria_id = cv.id
LEFT JOIN obra ob ON p.obra_id = ob.id
LEFT JOIN persona pe ON p.persona_beneficiaria_id = pe.id
"""


def get_conn():
    return sqlite3.connect(str(DB), check_same_thread=False)


def query(sql, params=()):
    conn = get_conn()
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    return [dict(zip(cols, r)) for r in rows]


def query_one(sql, params=()):
    r = query(sql, params)
    return r[0] if r else None


def sanitize_fts(q):
    """Convert user input into a safe FTS5 query.

    Splits on whitespace, keeps alphanumerics + accented letters,
    quotes each token and appends '*' for prefix matching. Tokens
    are joined with implicit AND.
    Returns empty string if no valid tokens remain (e.g. user typed
    only punctuation like 'S/').
    """
    keep = set("áéíóúüñÁÉÍÓÚÜÑ")
    tokens = []
    for w in q.split():
        cleaned = "".join(c for c in w if c.isalnum() or c in keep)
        if cleaned:
            tokens.append(f'"{cleaned}"*')
    return " ".join(tokens)


def build_page_url(p, current_args):
    args = dict(current_args)
    args["p"] = str(p)
    return "/?" + urllib.parse.urlencode(args)


@app.route("/")
def index():
    q, yf_val, yt_val, la, rf, mf, otf, tp, mm_val, mmn_val, adv = parse_filters()

    anios_list = [r["anio"] for r in query("SELECT anio FROM convocatoria WHERE anio > 0 ORDER BY anio")]
    lineas_rows = query("SELECT codigo, nombre_canonico FROM linea_concursable ORDER BY codigo")
    lineas_list = [r["codigo"] for r in lineas_rows]
    lineas_dict = {r["codigo"]: r["nombre_canonico"] for r in lineas_rows}
    modalidad_list = [r["nombre"] for r in query("SELECT DISTINCT nombre FROM modalidad WHERE nombre != '' ORDER BY nombre")]
    obra_tipo_list = [r["tipo"] for r in query("SELECT DISTINCT tipo FROM obra WHERE tipo IS NOT NULL AND tipo != '' ORDER BY tipo")]
    raw_regions = query(
        "SELECT DISTINCT pe.region FROM proyecto p "
        "JOIN persona pe ON p.persona_beneficiaria_id = pe.id "
        "WHERE pe.region != '' AND pe.region IS NOT NULL"
    )
    canonical_regions = set()
    for r in raw_regions:
        resolved = resolve_region(r["region"])
        if resolved:
            canonical_regions.add(resolved.upper())
    region_list = sorted(canonical_regions)
    total_db = query_one("SELECT COUNT(*) as c FROM proyecto")["c"]
    monto_sum = query_one("SELECT SUM(monto_otorgado) as s FROM proyecto")["s"]
    monto_db = f"S/ {monto_sum:,.2f}"

    suggestions = ["CPF", "documental", "Lima", "animación", "2024", "ficción"]

    return render_template(
        "index.html",
        anios=anios_list,
        lineas=lineas_list,
        lineas_dict=lineas_dict,
        regiones=region_list,
        modalidades=modalidad_list,
        obra_tipos=obra_tipo_list,
        obra_tipo_labels=OBRA_TIPO_LABELS,
        total_db=total_db,
        monto_db=monto_db,
        q=q,
        yf=yf_val or anios_list[0],
        yt=yt_val or anios_list[-1],
        la=la,
        rf=rf,
        mf=mf,
        otf=otf,
        tp=tp,
        mm=mm_val,
        mmn=mmn_val,
        suggestions=suggestions,
    )


# ── SHARED FILTER PARSER ──────────────────────────────────────────────
def parse_filters():
    q = request.args.get("q", "").strip()
    yf = request.args.get("yf", "")
    yt = request.args.get("yt", "")
    la = [x for x in request.args.getlist("la") if x]
    rf = [x for x in request.args.getlist("rf") if x]
    mf = [x for x in request.args.getlist("mf") if x]
    otf = [x for x in request.args.getlist("otf") if x]
    tp = request.args.get("tp", "")
    mm = request.args.get("mm", "999999999")
    mmn = request.args.get("mmn", "0")
    adv = request.args.get("adv", "")
    try:
        mm_val = int(mm)
    except (TypeError, ValueError):
        mm_val = 999999999
    try:
        mmn_val = int(mmn)
    except (TypeError, ValueError):
        mmn_val = 0
    try:
        yf_val = int(yf) if yf else None
    except (TypeError, ValueError):
        yf_val = None
    try:
        yt_val = int(yt) if yt else None
    except (TypeError, ValueError):
        yt_val = None
    return q, yf_val, yt_val, la, rf, mf, otf, tp, mm_val, mmn_val, adv


def build_base_where(params, mmn_val, mm_val, tp, yf_val, yt_val, la, rf, mf, otf):
    base_where = ["p.monto_otorgado >= ?", "p.monto_otorgado <= ?"]
    base_params = [mmn_val, mm_val]
    if tp:
        base_where.append("pe.tipo = ?")
        base_params.append(tp)

    def add_rf(w, p):
        if rf:
            like_clauses = " OR ".join("UPPER(pe.region) = ? OR UPPER(pe.region) LIKE ?" for _ in rf)
            w.append(f"({like_clauses})")
            for reg in rf:
                p.append(reg); p.append(f"{reg}%")

    def add_mf(w, p):
        if mf:
            ph = ",".join("?" for _ in mf)
            w.append(f"p.modalidad_id IN (SELECT m.id FROM modalidad m WHERE m.nombre IN ({ph}))")
            p.extend(mf)

    def add_yf(w, p):
        if yf_val:
            w.append("cv.anio >= ?"); p.append(yf_val)

    def add_yt(w, p):
        if yt_val:
            w.append("cv.anio <= ?"); p.append(yt_val)

    def add_la(w, p):
        if la:
            ph = ",".join("?" for _ in la)
            w.append(f"lc.codigo IN ({ph})")
            p.extend(la)

    def add_otf(w, p):
        if otf:
            ph = ",".join("?" for _ in otf)
            w.append(f"ob.tipo IN ({ph})")
            p.extend(otf)

    where = list(base_where)
    params = list(base_params)
    add_yf(where, params)
    add_yt(where, params)
    add_la(where, params)
    add_rf(where, params)
    add_mf(where, params)
    add_otf(where, params)
    return where, params


# ── DASHBOARD API ──────────────────────────────────────────────────────
@app.route("/api/dashboard")
def api_dashboard():
    q, yf_val, yt_val, la, rf, mf, otf, tp, mm_val, mmn_val, adv = parse_filters()

    fts_q = sanitize_fts(q) if q else ""
    fts_clause = ""
    fts_params = []
    if fts_q:
        fts_clause = (
            "JOIN (SELECT proyecto_id, "
            f"bm25(proyecto_fts, {BM25_WEIGHTS}) AS rank "
            "FROM proyecto_fts WHERE proyecto_fts MATCH ?) fts "
            "ON fts.proyecto_id = p.id"
        )
        fts_params = [fts_q]

    where, params = build_base_where([], mmn_val, mm_val, tp, yf_val, yt_val, la, rf, mf, otf)
    where_sql = " AND ".join(where)

    # 1. Proyectos por año
    data_anio_cnt = query(
        "SELECT cv.anio, COUNT(DISTINCT p.id) as cnt "
        + BASE_FROM.format(fts=fts_clause)
        + f" WHERE {where_sql} GROUP BY cv.anio ORDER BY cv.anio",
        fts_params + params,
    )

    # 2. Monto por año
    data_anio_monto = query(
        "SELECT cv.anio, COALESCE(SUM(p.monto_otorgado),0) as total "
        + BASE_FROM.format(fts=fts_clause)
        + f" WHERE {where_sql} GROUP BY cv.anio ORDER BY cv.anio",
        fts_params + params,
    )

    # 3. Top modalidades
    data_modal = query(
        "SELECT m.nombre, COUNT(DISTINCT p.id) as cnt, COALESCE(SUM(p.monto_otorgado),0) as total "
        + BASE_FROM.format(fts=fts_clause)
        + " LEFT JOIN modalidad m ON p.modalidad_id = m.id"
        + f" WHERE m.nombre IS NOT NULL AND m.nombre != '' AND {where_sql} "
        "GROUP BY m.nombre ORDER BY total DESC LIMIT 12",
        fts_params + params,
    )

    # 4. Departamentos (sin LIMIT para que el mapa muestre todas las regiones)
    raw_dpto = query(
        "SELECT COALESCE(NULLIF(pe.region,''),'SIN DATO') as dpto, "
        "COUNT(DISTINCT p.id) as cnt, COALESCE(SUM(p.monto_otorgado),0) as total "
        + BASE_FROM.format(fts=fts_clause)
        + f" WHERE {where_sql} "
        "GROUP BY dpto ORDER BY cnt DESC",
        fts_params + params,
    )
    dpto_facets = {}
    dpto_monto = {}
    for r in raw_dpto:
        resolved = resolve_region(r["dpto"]) if r["dpto"] != "SIN DATO" else ""
        if resolved:
            key = _strip_accents(resolved.upper())
        else:
            key = r["dpto"]
        dpto_facets[key] = dpto_facets.get(key, 0) + r["cnt"]
        dpto_monto[key] = dpto_monto.get(key, 0) + r["total"]
    data_dpto = [{"dpto": REGION_CANON.get(k, k), "cnt": v, "total": dpto_monto.get(k, 0)}
                 for k, v in sorted(dpto_facets.items(), key=lambda x: -x[1])]

    # 5. Tipo persona
    data_tipo = query(
        "SELECT COALESCE(pe.tipo,'sin dato') as tipo, COUNT(DISTINCT p.id) as cnt, "
        "COALESCE(SUM(p.monto_otorgado),0) as total "
        + BASE_FROM.format(fts=fts_clause)
        + f" WHERE {where_sql} GROUP BY pe.tipo",
        fts_params + params,
    )

    # 6. Línea x año (stacked)
    data_linea_anio = query(
        "SELECT cv.anio, lc.codigo, COUNT(DISTINCT p.id) as cnt "
        + BASE_FROM.format(fts=fts_clause)
        + f" WHERE {where_sql} "
        "GROUP BY cv.anio, lc.codigo ORDER BY cv.anio, cnt DESC",
        fts_params + params,
    )

    # 7. Obra tipo distribution
    data_obra_tipo = query(
        "SELECT COALESCE(ob.tipo,'sin_dato') as tipo, "
        "COUNT(DISTINCT p.id) as cnt, COALESCE(SUM(p.monto_otorgado),0) as total "
        + BASE_FROM.format(fts=fts_clause)
        + f" WHERE ob.tipo IS NOT NULL AND ob.tipo != '' AND ob.tipo != 'sin_dato' AND {where_sql} "
        "GROUP BY ob.tipo ORDER BY total DESC",
        fts_params + params,
    )

    # 8. Monto ranges histogram
    data_monto_ranges = query(
        "SELECT "
        "CASE "
        "  WHEN p.monto_otorgado < 10000 THEN '0-10K' "
        "  WHEN p.monto_otorgado < 30000 THEN '10K-30K' "
        "  WHEN p.monto_otorgado < 50000 THEN '30K-50K' "
        "  WHEN p.monto_otorgado < 100000 THEN '50K-100K' "
        "  WHEN p.monto_otorgado < 200000 THEN '100K-200K' "
        "  ELSE '200K+' "
        "END as rango, "
        "COUNT(DISTINCT p.id) as cnt, COALESCE(SUM(p.monto_otorgado),0) as total "
        + BASE_FROM.format(fts=fts_clause)
        + f" WHERE {where_sql} "
        "GROUP BY rango ORDER BY MIN(p.monto_otorgado)",
        fts_params + params,
    )

    # 9. Línea x año with both count and sum
    data_linea_evolucion = query(
        "SELECT cv.anio, lc.codigo, "
        "COUNT(DISTINCT p.id) as cnt, COALESCE(SUM(p.monto_otorgado),0) as total "
        + BASE_FROM.format(fts=fts_clause)
        + f" WHERE {where_sql} "
        "GROUP BY cv.anio, lc.codigo ORDER BY cv.anio, lc.codigo",
        fts_params + params,
    )

    # 10. Línea resumen
    data_linea_resumen = query(
        "SELECT lc.codigo, "
        "COUNT(DISTINCT p.id) as cnt, COALESCE(SUM(p.monto_otorgado),0) as total "
        + BASE_FROM.format(fts=fts_clause)
        + f" WHERE {where_sql} "
        "GROUP BY lc.codigo ORDER BY total DESC",
        fts_params + params,
    )

    # 11. KPIs
    kpi = query_one(
        "SELECT COUNT(DISTINCT p.id) as total_proy, "
        "COALESCE(SUM(p.monto_otorgado),0) as total_monto, "
        "COALESCE(MAX(p.monto_otorgado),0) as max_monto, "
        "COALESCE(MIN(p.monto_otorgado),0) as min_monto "
        + BASE_FROM.format(fts=fts_clause) + f" WHERE {where_sql}",
        fts_params + params,
    )

    return jsonify(
        anio_cnt=data_anio_cnt,
        anio_monto=data_anio_monto,
        modal=data_modal,
        dpto=data_dpto,
        tipo=data_tipo,
        linea_anio=data_linea_anio,
        obra_tipo=data_obra_tipo,
        monto_ranges=data_monto_ranges,
        linea_evolucion=data_linea_evolucion,
        linea_resumen=data_linea_resumen,
        kpi=kpi,
    )


# ── DASHBOARD PAGE ─────────────────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    q, yf_val, yt_val, la, rf, mf, otf, tp, mm_val, mmn_val, adv = parse_filters()

    anios_list = [r["anio"] for r in query("SELECT anio FROM convocatoria WHERE anio > 0 ORDER BY anio")]
    lineas_rows = query("SELECT codigo, nombre_canonico FROM linea_concursable ORDER BY codigo")
    lineas_list = [r["codigo"] for r in lineas_rows]
    lineas_dict = {r["codigo"]: r["nombre_canonico"] for r in lineas_rows}
    modalidad_list = [r["nombre"] for r in query("SELECT DISTINCT nombre FROM modalidad WHERE nombre != '' ORDER BY nombre")]
    obra_tipo_list = [r["tipo"] for r in query("SELECT DISTINCT tipo FROM obra WHERE tipo IS NOT NULL AND tipo != '' ORDER BY tipo")]
    raw_regions = query(
        "SELECT DISTINCT pe.region FROM proyecto p "
        "JOIN persona pe ON p.persona_beneficiaria_id = pe.id "
        "WHERE pe.region != '' AND pe.region IS NOT NULL"
    )
    canonical_regions = set()
    for r in raw_regions:
        resolved = resolve_region(r["region"])
        if resolved:
            canonical_regions.add(resolved.upper())
    region_list = sorted(canonical_regions)
    total_db = query_one("SELECT COUNT(*) as c FROM proyecto")["c"]
    monto_sum = query_one("SELECT SUM(monto_otorgado) as s FROM proyecto")["s"]
    monto_db = f"S/ {monto_sum:,.2f}"

    return render_template(
        "dashboard.html",
        anios=anios_list,
        lineas=lineas_list,
        lineas_dict=lineas_dict,
        regiones=region_list,
        modalidades=modalidad_list,
        obra_tipos=obra_tipo_list,
        obra_tipo_labels=OBRA_TIPO_LABELS,
        total_db=total_db,
        monto_db=monto_db,
        yf=yf_val or anios_list[0],
        yt=yt_val or anios_list[-1],
        la=la,
        rf=rf,
        mf=mf,
        otf=otf,
        tp=tp,
        mm=mm_val,
        mmn=mmn_val,
    )


# ── SEARCH API (JSON) ──────────────────────────────────────────────────
@app.route("/api/search")
def api_search():
    q, yf_val, yt_val, la, rf, mf, otf, tp, mm_val, mmn_val, adv = parse_filters()
    page = int(request.args.get("p", 1))

    fts_q = sanitize_fts(q) if q else ""
    fts_clause = ""
    fts_params = []
    if fts_q:
        fts_clause = (
            "JOIN (SELECT proyecto_id, "
            f"bm25(proyecto_fts, {BM25_WEIGHTS}) AS rank "
            "FROM proyecto_fts WHERE proyecto_fts MATCH ?) fts "
            "ON fts.proyecto_id = p.id"
        )
        fts_params = [fts_q]

    where, params = build_base_where([], mmn_val, mm_val, tp, yf_val, yt_val, la, rf, mf, otf)
    where_sql = " AND ".join(where)

    total = query_one(
        "SELECT COUNT(DISTINCT p.id) as c "
        + BASE_FROM.format(fts=fts_clause) + f" WHERE {where_sql}",
        fts_params + params,
    )["c"]

    per_page = 25
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = 1
    offset = (page - 1) * per_page

    order = "fts.rank ASC" if fts_q else "cv.anio DESC, lc.codigo"
    rows = query(
        "SELECT p.id, p.concurso_anual_id, cv.anio, lc.codigo as linea, "
        "ca.nombre_usado as concurso_nombre, "
        "ob.titulo, ob.tipo as obra_tipo, "
        "pe.nombres, pe.apellidos, pe.tipo as tipo_per, pe.region as region, pe.razon_social, "
        "p.monto_otorgado as monto, "
        "p.modalidad_id, "
        "(SELECT m2.nombre FROM modalidad m2 WHERE m2.id = p.modalidad_id) as modalidad, "
        "(SELECT r.numero FROM resolucion r "
        "JOIN proyecto_resolucion rp ON r.id = rp.resolucion_id "
        "WHERE rp.proyecto_id = p.id "
        "ORDER BY CASE r.tipo WHEN 'resolucion_beneficiario' THEN 1 WHEN 'fallo_final' THEN 2 ELSE 3 END "
        "LIMIT 1) as rd "
        + BASE_FROM.format(fts=fts_clause)
        + f" WHERE {where_sql} ORDER BY {order} LIMIT ? OFFSET ?",
        fts_params + params + [per_page, offset],
    )

    lineas_rows = query("SELECT codigo, nombre_canonico FROM linea_concursable ORDER BY codigo")
    lineas_dict = {r["codigo"]: r["nombre_canonico"] for r in lineas_rows}

    # Batch-fetch jurados for all distinct concurso_anual_id values
    ca_ids = list(set(r["concurso_anual_id"] for r in rows))
    jurados_by_ca = {}
    if ca_ids:
        placeholders = ",".join("?" for _ in ca_ids)
        jurados_raw = query(
            "SELECT j.concurso_anual_id, p.nombres, p.apellidos, p.razon_social, p.tipo, j.cargo "
            "FROM jurado j JOIN persona p ON j.persona_id = p.id "
            f"WHERE j.concurso_anual_id IN ({placeholders}) "
            "ORDER BY j.concurso_anual_id, j.cargo",
            ca_ids,
        )
        for j in jurados_raw:
            ca_id = j["concurso_anual_id"]
            if ca_id not in jurados_by_ca:
                jurados_by_ca[ca_id] = []
            if j["tipo"] == "juridica":
                name = j["razon_social"] or "—"
            else:
                name = f"{j['nombres'] or ''} {j['apellidos'] or ''}".strip() or "—"
            jurados_by_ca[ca_id].append(f"{name} ({j['cargo'] or '—'})")

    results = []
    for r in rows:
        is_juridica = r["tipo_per"] == "juridica"
        if is_juridica:
            nombre = r["razon_social"] or "—"
            persona_label = "Razón social"
        else:
            nombre = f"{r['nombres'] or ''} {r['apellidos'] or ''}".strip() or "—"
            persona_label = "Director"
        titulo = r["titulo"] or "—"
        monto_fmt = f"S/ {r['monto']:,.2f}" if r["monto"] else "—"
        rd = r["rd"] or "—"
        tipo_label = "Persona jurídica" if is_juridica else "Persona natural"

        ints = query(
            "SELECT pe.nombres, pe.apellidos, pe.razon_social, pe.tipo, pi.rol "
            "FROM proyecto_integrante pi "
            "JOIN persona pe ON pi.persona_id = pe.id WHERE pi.proyecto_id = ?",
            [r["id"]],
        )
        integrantes = []
        for i in ints:
            if i["tipo"] == "juridica":
                name = i["razon_social"] or "—"
            else:
                name = f"{i['nombres'] or ''} {i['apellidos'] or ''}".strip() or "—"
            integrantes.append(f"{name} ({i['rol'] or '—'})")

        res = query_one(
            "SELECT r.numero, r.tipo, r.id as rid, r.url_pdf FROM resolucion r "
            "JOIN proyecto_resolucion rp ON r.id = rp.resolucion_id "
            "WHERE rp.proyecto_id = ? "
            "ORDER BY CASE r.tipo WHEN 'resolucion_beneficiario' THEN 1 WHEN 'fallo_final' THEN 2 ELSE 3 END "
            "LIMIT 1",
            [r["id"]],
        )
        resolucion = f"{res['numero']} ({res['tipo']})" if res else None
        pdf_url = res["url_pdf"] if res else None

        region_raw = r.get("region") or ""
        region_resolved = resolve_region(region_raw)
        obra_tipo = r["obra_tipo"] or ""
        results.append({
            "titulo": titulo,
            "persona": html.escape(nombre),
            "persona_label": persona_label,
            "monto": monto_fmt,
            "rd": html.escape(rd),
            "linea": r["linea"],
            "linea_nombre": lineas_dict.get(r["linea"], r["linea"]),
            "anio": int(r["anio"]),
            "tipo_label": tipo_label,
            "obra_tipo": obra_tipo,
            "obra_tipo_label": OBRA_TIPO_LABELS.get(obra_tipo, obra_tipo.title() if obra_tipo else "—"),
            "region": html.escape(region_resolved or region_raw or "—"),
            "modalidad": "-" if r.get("modalidad") and r.get("modalidad") == r.get("concurso_nombre") else html.escape(r.get("modalidad") or "—"),
            "integrantes": integrantes,
            "jurados": jurados_by_ca.get(r["concurso_anual_id"], []),
            "resolucion": resolucion,
            "pdf_url": pdf_url,
        })

    return jsonify(results=results, total=total, page=page, total_pages=total_pages)


# ── FILTERS API (cascading) ────────────────────────────────────────────
@app.route("/api/filters")
def api_filters():
    q, yf_val, yt_val, la, rf, mf, otf, tp, mm_val, mmn_val, adv = parse_filters()

    fts_q = sanitize_fts(q) if q else ""
    fts_clause = ""
    fts_params = []
    if fts_q:
        fts_clause = (
            "JOIN (SELECT proyecto_id, "
            f"bm25(proyecto_fts, {BM25_WEIGHTS}) AS rank "
            "FROM proyecto_fts WHERE proyecto_fts MATCH ?) fts "
            "ON fts.proyecto_id = p.id"
        )
        fts_params = [fts_q]

    lineas_rows = query("SELECT codigo, nombre_canonico FROM linea_concursable ORDER BY codigo")
    lineas_dict = {r["codigo"]: r["nombre_canonico"] for r in lineas_rows}

    # Available years (always all)
    anios_all = [r["anio"] for r in query("SELECT anio FROM convocatoria WHERE anio > 0 ORDER BY anio")]

    # Common base WHERE for all filtered queries (excludes the filter being computed)
    def _base_where(exclude_cols):
        w = ["p.monto_otorgado >= ?", "p.monto_otorgado <= ?"]
        p = [mmn_val, mm_val]
        if tp and "tp" not in exclude_cols:
            w.append("pe.tipo = ?"); p.append(tp)
        if yf_val and "yf" not in exclude_cols:
            w.append("cv.anio >= ?"); p.append(yf_val)
        if yt_val and "yt" not in exclude_cols:
            w.append("cv.anio <= ?"); p.append(yt_val)
        if la and "la" not in exclude_cols:
            ph = ",".join("?" for _ in la)
            w.append(f"lc.codigo IN ({ph})"); p.extend(la)
        if rf and "rf" not in exclude_cols:
            like_clauses = " OR ".join("UPPER(pe.region) = ? OR UPPER(pe.region) LIKE ?" for _ in rf)
            w.append(f"({like_clauses})")
            for reg in rf:
                p.append(reg); p.append(f"{reg}%")
        if otf and "otf" not in exclude_cols:
            ph = ",".join("?" for _ in otf)
            w.append(f"ob.tipo IN ({ph})"); p.extend(otf)
        return w, p

    # Available categories
    cat_where, cat_params = _base_where(["otf"])
    categorias_avail = query(
        "SELECT ob.tipo, COUNT(DISTINCT p.id) as cnt "
        + BASE_FROM.format(fts=fts_clause)
        + f" WHERE ob.tipo IS NOT NULL AND ob.tipo != '' AND {' AND '.join(cat_where)} "
        "GROUP BY ob.tipo ORDER BY cnt DESC",
        fts_params + cat_params,
    )

    # Available lines
    la_where, la_params = _base_where(["la"])
    lineas_avail = query(
        "SELECT lc.codigo, COUNT(DISTINCT p.id) as cnt "
        + BASE_FROM.format(fts=fts_clause)
        + f" WHERE {' AND '.join(la_where)} "
        "GROUP BY lc.codigo ORDER BY cnt DESC, lc.codigo",
        fts_params + la_params,
    )

    # Available regions
    rf_where, rf_params = _base_where(["rf"])
    raw_regions = query(
        "SELECT pe.region, COUNT(DISTINCT p.id) as cnt "
        + BASE_FROM.format(fts=fts_clause)
        + f" WHERE pe.region != '' AND pe.region IS NOT NULL AND {' AND '.join(rf_where)} "
        "GROUP BY pe.region ORDER BY cnt DESC",
        fts_params + rf_params,
    )
    region_facets = {}
    for r in raw_regions:
        resolved = resolve_region(r["region"])
        if resolved:
            key = _strip_accents(resolved.upper())
            region_facets[key] = region_facets.get(key, 0) + r["cnt"]
    region_avail = [{"region": REGION_CANON.get(k, k), "cnt": v}
                    for k, v in sorted(region_facets.items(), key=lambda x: -x[1])]

    return jsonify(
        anios=[{"anio": y} for y in anios_all],
        categorias=[{"codigo": r["tipo"], "nombre": OBRA_TIPO_LABELS.get(r["tipo"], r["tipo"]), "cnt": r["cnt"]} for r in categorias_avail],
        lineas=[{"codigo": r["codigo"], "nombre": lineas_dict.get(r["codigo"], r["codigo"]), "cnt": r["cnt"]} for r in lineas_avail],
        regiones=region_avail,
    )


# ── MAPA PAGE ─────────────────────────────────────────────────────────
@app.route("/mapa")
def mapa():
    q, yf_val, yt_val, la, rf, mf, otf, tp, mm_val, mmn_val, adv = parse_filters()

    anios_list = [r["anio"] for r in query("SELECT anio FROM convocatoria WHERE anio > 0 ORDER BY anio")]
    lineas_rows = query("SELECT codigo, nombre_canonico FROM linea_concursable ORDER BY codigo")
    lineas_list = [r["codigo"] for r in lineas_rows]
    lineas_dict = {r["codigo"]: r["nombre_canonico"] for r in lineas_rows}
    modalidad_list = [r["nombre"] for r in query("SELECT DISTINCT nombre FROM modalidad WHERE nombre != '' ORDER BY nombre")]
    obra_tipo_list = [r["tipo"] for r in query("SELECT DISTINCT tipo FROM obra WHERE tipo IS NOT NULL AND tipo != '' ORDER BY tipo")]
    raw_regions = query(
        "SELECT DISTINCT pe.region FROM proyecto p "
        "JOIN persona pe ON p.persona_beneficiaria_id = pe.id "
        "WHERE pe.region != '' AND pe.region IS NOT NULL"
    )
    canonical_regions = set()
    for r in raw_regions:
        resolved = resolve_region(r["region"])
        if resolved:
            canonical_regions.add(resolved.upper())
    region_list = sorted(canonical_regions)
    total_db = query_one("SELECT COUNT(*) as c FROM proyecto")["c"]
    monto_sum = query_one("SELECT SUM(monto_otorgado) as s FROM proyecto")["s"]
    monto_db = f"S/ {monto_sum:,.2f}"

    return render_template(
        "mapa.html",
        anios=anios_list,
        lineas=lineas_list,
        lineas_dict=lineas_dict,
        regiones=region_list,
        modalidades=modalidad_list,
        obra_tipos=obra_tipo_list,
        obra_tipo_labels=OBRA_TIPO_LABELS,
        total_db=total_db,
        monto_db=monto_db,
        q=q,
        yf=yf_val or anios_list[0],
        yt=yt_val or anios_list[-1],
        la=la,
        rf=rf,
        mf=mf,
        otf=otf,
        tp=tp,
        mm=mm_val,
        mmn=mmn_val,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8501, debug=False)
