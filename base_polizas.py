# -*- coding: utf-8 -*-
"""
Created on Wed Oct 29 13:03:04 2025

@author: rccorreall
"""

# app.py
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import uuid
import ssl
import time

# -------------------------
# SSL BYPASS (si es necesario)
# -------------------------
# Esto evita errores en entornos muy restringidos; úsalo solo si lo necesitas.
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass

# -------------------------
# Config Streamlit / Estilo
# -------------------------
st.set_page_config(page_title="Gestor de Pólizas - base_polizas", layout="wide")
st.title("📄 Gestor de Prospectos y Pólizas — base_polizas")

st.markdown(
    """
App para gestionar **Prospectos** y **Pólizas** con Google Sheets.
- Crear / editar / duplicar pólizas.
- Convertir prospectos en pólizas.
- Fechas con calendario y selects desde catálogos (con opción de agregar).
- Listado de pólizas que vencen en los próximos 30 días.
""",
    unsafe_allow_html=True,
)

# -------------------------
# Constants / Configuración
# -------------------------
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SPREADSHEET_NAME = "base_polizas"
SHEET_POLIZAS = "Polizas"
SHEET_PROSPECTOS = "Prospectos"
SHEET_CATALOGS = "Catalogos"

# -------------------------
# Conexión a Google Sheets
# -------------------------
if "google_service_account" not in st.secrets:
    st.error("Falta st.secrets['google_service_account']. Añade el JSON de la cuenta de servicio en Secrets.")
    st.stop()

@st.cache_resource(ttl=3600)
def connect_gs():
    try:
        creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=SCOPE)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Error autenticando Google Sheets: {e}")
        st.stop()

client = connect_gs()

# -------------------------
# Asegurar existencia de hojas y encabezados
# -------------------------
def ensure_sheets_and_headers():
    try:
        ss = client.open(SPREADSHEET_NAME)
    except Exception as e:
        st.error(f"No se pudo abrir el spreadsheet '{SPREADSHEET_NAME}'. Asegúrate que exista y que el service account tenga acceso. Error: {e}")
        st.stop()

    existing = [ws.title for ws in ss.worksheets()]

    # Encabezados por defecto
    poliza_headers = [
        "id", "fecha_registro", "numero_poliza", "producto", "asegurado_nombre",
        "asegurado_rfc", "vigencia_desde", "vigencia_hasta", "suma_asegurada",
        "prima", "canal", "agente", "observaciones"
    ]
    prospecto_headers = [
        "id", "fecha_registro", "nombre", "telefono", "email", "producto_interes",
        "agente_contacto", "notas"
    ]
    catalogs_initial = {
        "producto": ["Auto", "Hogar", "Vida"],
        "canal": ["Directo", "Broker", "Agente"],
        "agente": ["Agente A", "Agente B"]
    }

    # Crear si no existen
    if SHEET_POLIZAS not in existing:
        ss.add_worksheet(title=SHEET_POLIZAS, rows=1000, cols=len(poliza_headers))
        ws = ss.worksheet(SHEET_POLIZAS)
        ws.append_row(poliza_headers)

    if SHEET_PROSPECTOS not in existing:
        ss.add_worksheet(title=SHEET_PROSPECTOS, rows=1000, cols=len(prospecto_headers))
        ws = ss.worksheet(SHEET_PROSPECTOS)
        ws.append_row(prospecto_headers)

    if SHEET_CATALOGS not in existing:
        ss.add_worksheet(title=SHEET_CATALOGS, rows=100, cols=5)
        ws = ss.worksheet(SHEET_CATALOGS)
        # Crear columnas para cada catálogo en la primera fila
        # Escribimos cada catálogo en una columna (A1: producto, B1: canal, C1: agente)
        # y luego sus valores debajo
        # Preparar matriz por columnas (cada sublista es una columna)
        cols = []
        for k, vals in catalogs_initial.items():
            col = [k] + vals
            cols.append(col)
        # Transponer para update en rango rectangular
        max_len = max(len(c) for c in cols)
        table = []
        for r in range(max_len):
            row = []
            for c in cols:
                if r < len(c):
                    row.append(c[r])
                else:
                    row.append("")
            table.append(row)
        ws.update("A1", table)

ensure_sheets_and_headers()
ss = client.open(SPREADSHEET_NAME)
ws_polizas = ss.worksheet(SHEET_POLIZAS)
ws_prospectos = ss.worksheet(SHEET_PROSPECTOS)
ws_catalogs = ss.worksheet(SHEET_CATALOGS)

# -------------------------
# Helpers: cargar dataframes y catálogos
# -------------------------
@st.cache_data(ttl=300)
def load_ws_df(ws):
    data = ws.get_all_values()
    if not data or len(data) <= 1:
        return pd.DataFrame(columns=data[0] if data else [])
    df = pd.DataFrame(data[1:], columns=data[0])
    # intentar parsear fechas
    for c in ["vigencia_desde", "vigencia_hasta", "fecha_registro"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df

@st.cache_data(ttl=300)
def load_catalogs():
    vals = ws_catalogs.get_all_values()
    if not vals:
        return {}
    # Transponer: cada columna es un catálogo (encabezado + valores)
    df = pd.DataFrame(vals).T
    catalogs = {}
    for col in df.columns:
        colvals = df[col].dropna().tolist()
        if len(colvals) >= 1:
            key = colvals[0]
            catalogs[key] = colvals[1:]
    return catalogs

def add_to_catalog(cat_name, new_value):
    # buscar encabezado en fila 1
    first_row = ws_catalogs.row_values(1)
    try:
        idx = first_row.index(cat_name)  # 0-based
        col_index = idx + 1
    except ValueError:
        # agregar al final como nueva columna
        col_index = len(first_row) + 1
        ws_catalogs.update_cell(1, col_index, cat_name)
    col_values = ws_catalogs.col_values(col_index)
    next_row = len(col_values) + 1
    ws_catalogs.update_cell(next_row, col_index, new_value)
    load_catalogs.cache_clear()

def append_row_to_ws(ws, row_dict):
    headers = ws.row_values(1)
    row = [row_dict.get(h, "") for h in headers]
    ws.append_row(row)
    # limpiar caches
    if ws == ws_polizas:
        load_ws_df.cache_clear()
    elif ws == ws_prospectos:
        load_ws_df.cache_clear()

def update_row_by_sheet_index(ws, sheet_row_number, row_dict):
    headers = ws.row_values(1)
    row = [row_dict.get(h, "") for h in headers]
    last_col = chr(ord('A') + max(len(row)-1, 0))
    rng = f"A{sheet_row_number}:{last_col}{sheet_row_number}"
    ws.update(rng, [row])
    load_ws_df.cache_clear()

# Cargar DF
df_polizas = load_ws_df(ws_polizas)
df_prospectos = load_ws_df(ws_prospectos)
catalogs = load_catalogs()

# -------------------------
# Layout: sidebar acciones
# -------------------------
st.sidebar.title("Acciones")
action = st.sidebar.radio("Selecciona acción", [
    "Agregar Prospecto",
    "Convertir Prospecto a Póliza",
    "Agregar nueva Póliza",
    "Editar Póliza",
    "Duplicar / Renovar Póliza",
    "Pólizas por vencer (30 días)",
    "Explorar / Exportar"
])

# -------------------------
# Campos definiciones (ajustables)
# -------------------------
POLICY_FIELDS = [
    ("numero_poliza", "Número de Póliza", "text"),
    ("producto", "Producto", "select_producto"),
    ("asegurado_nombre", "Nombre del Asegurado", "text"),
    ("asegurado_rfc", "RFC", "text"),
    ("vigencia_desde", "Vigencia - Desde", "date"),
    ("vigencia_hasta", "Vigencia - Hasta", "date"),
    ("suma_asegurada", "Suma Asegurada", "number"),
    ("prima", "Prima", "number"),
    ("canal", "Canal", "select_canal"),
    ("agente", "Agente", "select_agente"),
    ("observaciones", "Observaciones", "text")
]

PROSPECT_FIELDS = [
    ("nombre", "Nombre", "text"),
    ("telefono", "Teléfono", "text"),
    ("email", "Email", "text"),
    ("producto_interes", "Producto de interés", "select_producto"),
    ("agente_contacto", "Agente contacto", "select_agente"),
    ("notas", "Notas", "text")
]

# -------------------------
# Acciones: Prospecto -> crear / convertir
# -------------------------
if action == "Agregar Prospecto":
    st.header("➕ Agregar Prospecto")
    with st.form("form_prospect"):
        vals = {}
        for key, label, ftype in PROSPECT_FIELDS:
            if ftype == "text":
                vals[key] = st.text_input(label, key=f"p_{key}")
            elif ftype.startswith("select"):
                cat = ftype.split("_")[1]
                options = catalogs.get(cat, [])
                add_opt_flag = f"__AGREGAR_NUEVO__{cat}"
                choices = [""] + options + [add_opt_flag]
                sel = st.selectbox(label, choices, key=f"p_{key}")
                if sel == add_opt_flag:
                    newv = st.text_input(f"Añadir nuevo {cat}", key=f"p_new_{cat}")
                    if newv:
                        add_to_catalog(cat, newv)
                        st.success(f"Agregado '{newv}' a catálogo {cat}. Vuelve a seleccionar.")
                        st.experimental_rerun()
                    vals[key] = ""
                else:
                    vals[key] = sel
        submitted = st.form_submit_button("Guardar Prospecto")
    if submitted:
        new_id = str(uuid.uuid4())
        tz = ZoneInfo("America/Mexico_City")
        now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        row = {"id": new_id, "fecha_registro": now}
        for k, _, _ in PROSPECT_FIELDS:
            row[k] = vals.get(k, "")
        append_row_to_ws(ws_prospectos, row)
        st.success("✅ Prospecto guardado.")
        st.experimental_rerun()

elif action == "Convertir Prospecto a Póliza":
    st.header("➡️ Convertir Prospecto a Póliza")
    if df_prospectos.empty:
        st.info("No hay prospectos registrados.")
    else:
        opciones = df_prospectos["nombre"].fillna("").tolist()
        sel = st.selectbox("Selecciona prospecto", [""] + opciones)
        if sel:
            src = df_prospectos[df_prospectos["nombre"] == sel].iloc[0].to_dict()
            st.write("Prospecto seleccionado:")
            st.write(src)
            with st.form("form_convert"):
                numero_pol = st.text_input("Número de Póliza (nuevo)", value=f"P-{int(time.time())%100000}")
                desde = st.date_input("Vigencia - Desde")
                hasta = st.date_input("Vigencia - Hasta")
                prima = st.number_input("Prima", min_value=0.0, format="%f")
                suma = st.number_input("Suma Asegurada", min_value=0.0, format="%f")
                submit_conv = st.form_submit_button("Crear Póliza desde Prospecto")
            if submit_conv:
                new_id = str(uuid.uuid4())
                tz = ZoneInfo("America/Mexico_City")
                now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
                row = {"id": new_id, "fecha_registro": now}
                # mapear campos del prospecto a póliza
                row["numero_poliza"] = numero_pol
                row["producto"] = src.get("producto_interes", "")
                row["asegurado_nombre"] = src.get("nombre", "")
                row["asegurado_rfc"] = ""  # vacío inicialmente
                row["vigencia_desde"] = desde.strftime("%Y-%m-%d")
                row["vigencia_hasta"] = hasta.strftime("%Y-%m-%d")
                row["suma_asegurada"] = suma
                row["prima"] = prima
                row["canal"] = ""  # opcional
                row["agente"] = src.get("agente_contacto", "")
                row["observaciones"] = src.get("notas", "")
                append_row_to_ws(ws_polizas, row)
                st.success("✅ Póliza creada desde prospecto.")
                st.experimental_rerun()

# -------------------------
# Acciones: Agregar, Editar, Duplicar póliza
# -------------------------
elif action == "Agregar nueva Póliza":
    st.header("➕ Agregar nueva Póliza")
    with st.form("form_add_pol"):
        values = {}
        for key, label, ftype in POLICY_FIELDS:
            if ftype == "text":
                values[key] = st.text_input(label, key=f"np_{key}")
            elif ftype == "number":
                values[key] = st.number_input(label, min_value=0.0, format="%f", key=f"np_{key}")
            elif ftype == "date":
                values[key] = st.date_input(label, key=f"np_{key}")
            elif ftype.startswith("select"):
                cat_name = ftype.split("_")[1]
                options = catalogs.get(cat_name, [])
                add_new_opt = f"__AGREGAR_NUEVO___{cat_name}"
                choices = [""] + options + [add_new_opt]
                sel = st.selectbox(label, choices, key=f"np_{key}")
                if sel == add_new_opt:
                    new_val = st.text_input(f"Añadir nuevo {cat_name}", key=f"np_new_{cat_name}")
                    if new_val:
                        add_to_catalog(cat_name, new_val)
                        st.success(f"Agregado '{new_val}' a catálogo {cat_name}. Vuelve a seleccionar.")
                        st.experimental_rerun()
                    values[key] = ""
                else:
                    values[key] = sel
        submitted = st.form_submit_button("Guardar póliza")
    if submitted:
        new_id = str(uuid.uuid4())
        tz = ZoneInfo("America/Mexico_City")
        now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        # formatear fechas
        for k, _, t in POLICY_FIELDS:
            if t == "date" and isinstance(values.get(k), (pd.Timestamp, datetime)):
                values[k] = values[k].strftime("%Y-%m-%d")
        row = {"id": new_id, "fecha_registro": now}
        for k, _, _ in POLICY_FIELDS:
            row[k] = values.get(k, "")
        append_row_to_ws(ws_polizas, row)
        st.success("✅ Póliza guardada correctamente.")
        st.experimental_rerun()

elif action == "Editar Póliza":
    st.header("✏️ Editar Póliza")
    if df_polizas.empty:
        st.info("No hay pólizas registradas.")
    else:
        opciones = df_polizas["numero_poliza"].fillna("").tolist()
        sel = st.selectbox("Selecciona número de póliza", [""] + opciones)
        if sel:
            row = df_polizas[df_polizas["numero_poliza"] == sel].iloc[0]
            row_index = df_polizas[df_polizas["numero_poliza"] == sel].index[0]
            sheet_row_number = int(row_index) + 2  # header + 1
            with st.form("form_edit_pol"):
                new_vals = {}
                for key, label, ftype in POLICY_FIELDS:
                    cur = row.get(key, "")
                    if ftype == "text":
                        new_vals[key] = st.text_input(label, value=cur, key=f"ed_{key}")
                    elif ftype == "number":
                        try:
                            init = float(cur) if cur not in [None, ""] else 0.0
                        except:
                            init = 0.0
                        new_vals[key] = st.number_input(label, value=init, key=f"ed_{key}")
                    elif ftype == "date":
                        try:
                            init = pd.to_datetime(cur).date() if pd.notna(cur) and cur != "" else None
                        except:
                            init = None
                        new_vals[key] = st.date_input(label, value=init, key=f"ed_{key}")
                    elif ftype.startswith("select"):
                        cat_name = ftype.split("_")[1]
                        options = catalogs.get(cat_name, [])
                        add_new_opt = f"__AGREGAR_NUEVO___{cat_name}"
                        choices = [""] + options + [add_new_opt]
                        cur_sel = cur if cur in options else ""
                        selbox = st.selectbox(label, choices, index=choices.index(cur_sel) if cur_sel in choices else 0, key=f"ed_{key}")
                        if selbox == add_new_opt:
                            newv = st.text_input(f"Añadir nuevo {cat_name}", key=f"ed_new_{cat_name}")
                            if newv:
                                add_to_catalog(cat_name, newv)
                                st.success(f"Agregado '{newv}' a catálogo {cat_name}. Vuelve a seleccionar.")
                                st.experimental_rerun()
                            new_vals[key] = ""
                        else:
                            new_vals[key] = selbox
                save = st.form_submit_button("Guardar cambios")
            if save:
                # preparar fila completa
                headers = ws_polizas.row_values(1)
                updated = {}
                # preservar id y fecha_registro original
                updated["id"] = row["id"]
                updated["fecha_registro"] = row["fecha_registro"].strftime("%Y-%m-%d %H:%M:%S") if pd.notna(row["fecha_registro"]) else ""
                for k, _, t in POLICY_FIELDS:
                    val = new_vals.get(k, "")
                    if t == "date" and isinstance(val, (datetime, )):
                        val = val.strftime("%Y-%m-%d")
                    updated[k] = val
                update_row_by_sheet_index(ws_polizas, sheet_row_number, updated)
                st.success("✅ Póliza actualizada.")
                st.experimental_rerun()

elif action == "Duplicar / Renovar Póliza":
    st.header("🔁 Duplicar / Renovar Póliza")
    if df_polizas.empty:
        st.info("No hay pólizas registradas.")
    else:
        choices = df_polizas["numero_poliza"].fillna("").tolist()
        sel = st.selectbox("Selecciona póliza a duplicar", [""] + choices)
        if sel:
            src = df_polizas[df_polizas["numero_poliza"] == sel].iloc[0].to_dict()
            st.write("Póliza origen:")
            st.write(src)
            with st.form("form_dup"):
                new_num = st.text_input("Nuevo número de póliza", value=f"{sel}_REN")
                try:
                    default_desde = (pd.to_datetime(src.get("vigencia_desde")) + pd.Timedelta(days=365)).date() if src.get("vigencia_desde") not in [None, ""] else None
                    default_hasta = (pd.to_datetime(src.get("vigencia_hasta")) + pd.Timedelta(days=365)).date() if src.get("vigencia_hasta") not in [None, ""] else None
                except Exception:
                    default_desde = None
                    default_hasta = None
                new_desde = st.date_input("Nueva vigencia - Desde", value=default_desde)
                new_hasta = st.date_input("Nueva vigencia - Hasta", value=default_hasta)
                submit_dup = st.form_submit_button("Crear póliza duplicada")
            if submit_dup:
                new_id = str(uuid.uuid4())
                tz = ZoneInfo("America/Mexico_City")
                now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
                row = {"id": new_id, "fecha_registro": now}
                for k, _, _ in POLICY_FIELDS:
                    if k == "numero_poliza":
                        row[k] = new_num
                    elif k == "vigencia_desde":
                        row[k] = new_desde.strftime("%Y-%m-%d") if new_desde else ""
                    elif k == "vigencia_hasta":
                        row[k] = new_hasta.strftime("%Y-%m-%d") if new_hasta else ""
                    else:
                        row[k] = src.get(k, "")
                append_row_to_ws(ws_polizas, row)
                st.success("✅ Póliza duplicada creada.")
                st.experimental_rerun()

# -------------------------
# Pólizas por vencer
# -------------------------
elif action == "Pólizas por vencer (30 días)":
    st.header("⏰ Pólizas por vencer en los próximos 30 días")
    if df_polizas.empty:
        st.info("No hay pólizas registradas.")
    else:
        today = datetime.now(ZoneInfo("America/Mexico_City")).date()
        cutoff = today + timedelta(days=30)
        if "vigencia_hasta" in df_polizas.columns:
            mask = (df_polizas["vigencia_hasta"].notna()) & (df_polizas["vigencia_hasta"].dt.date >= today) & (df_polizas["vigencia_hasta"].dt.date <= cutoff)
            close = df_polizas[mask].copy()
            if not close.empty:
                close["dias_para_vencer"] = (close["vigencia_hasta"].dt.date - today).apply(lambda x: x.days)
                st.write(f"Pólizas que vencen entre {today} y {cutoff}: {len(close)}")
                st.dataframe(close[["numero_poliza", "asegurado_nombre", "vigencia_hasta", "dias_para_vencer", "agente", "canal"]])
                # ejemplo: botón para exportar a CSV las que vencen
                csv = close.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Descargar CSV (por vencer)", data=csv, file_name="polizas_por_vencer.csv", mime="text/csv")
            else:
                st.info("No hay pólizas próximas a vencer en ese rango.")
        else:
            st.info("No existe columna 'vigencia_hasta' en Polizas.")

# -------------------------
# Explorar / Exportar
# -------------------------
elif action == "Explorar / Exportar":
    st.header("🔎 Explorar datos")
    st.subheader("Prospectos")
    st.dataframe(df_prospectos)
    csvp = df_prospectos.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Descargar Prospectos CSV", data=csvp, file_name="prospectos.csv", mime="text/csv")

    st.subheader("Pólizas")
    st.dataframe(df_polizas)
    csv = df_polizas.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Descargar Pólizas CSV", data=csv, file_name="polizas.csv", mime="text/csv")

# -------------------------
# Pie: instrucciones / notas
# -------------------------
st.markdown("---")
st.markdown("**Notas de configuración**")
st.markdown("""
- Añade en `st.secrets`:
  - `google_service_account`: el JSON de la cuenta de servicio (objeto JSON completo).
- Asegúrate que el `service account` tenga acceso (al menos permiso de edición) al Google Sheet llamado **base_polizas**.
- El script crea automáticamente 3 hojas: `Prospectos`, `Polizas` y `Catalogos` si no existen.
- Recomendaciones:
  - Validar unicidad de `numero_poliza` si lo requieres.
  - Manejar tipos numéricos y monedas según tu formato (local).
  - Si varios usuarios editarán simultáneamente, considera bloqueo/locking o una tabla de auditoría.
""")
