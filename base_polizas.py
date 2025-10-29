import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import ssl

# ============================================================
# BYPASS SSL (algunos entornos de Streamlit lo requieren)
# ============================================================
ssl._create_default_https_context = ssl._create_unverified_context

# ============================================================
# CONFIGURACIÓN DE GOOGLE SHEETS DESDE STREAMLIT SECRETS
# ============================================================
# En Streamlit.io ve a: Settings → Secrets → Add secret
# Pega tu JSON completo de cuenta de servicio con la clave "gcp_service_account"
# Ejemplo:
# [gcp_service_account]
# type = "service_account"
# project_id = "..."
# private_key_id = "..."
# private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
# client_email = "..."
# client_id = "..."
# token_uri = "https://oauth2.googleapis.com/token"

# Cargamos las credenciales directamente desde los secrets
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)

# Autenticamos cliente de Google Sheets
client = gspread.authorize(creds)

# ============================================================
# CONECTAR A TU GOOGLE SHEET
# ============================================================
SPREADSHEET_NAME = "base_polizas"

try:
    sheet = client.open(SPREADSHEET_NAME)
except gspread.SpreadsheetNotFound:
    st.error(f"No se encontró el archivo '{SPREADSHEET_NAME}' en tu cuenta de Google.")
    st.stop()

# ============================================================
# CREAR HOJAS SI NO EXISTEN
# ============================================================
def ensure_sheet_exists(sheet, title, header):
    """Crea la hoja si no existe, con los encabezados dados."""
    try:
        worksheet = sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=title, rows="100", cols=str(len(header)))
        worksheet.append_row(header)
    return worksheet

prospectos_ws = ensure_sheet_exists(sheet, "Prospectos", ["Nombre", "Correo", "Teléfono", "Producto"])
polizas_ws = ensure_sheet_exists(sheet, "Polizas", ["Nombre", "Correo", "Teléfono", "Producto"])

# ============================================================
# FUNCIONES DE APP
# ============================================================
def agregar_prospecto(nombre, correo, telefono, producto):
    prospectos_ws.append_row([nombre, correo, telefono, producto])

def convertir_a_poliza(nombre):
    data = prospectos_ws.get_all_records()
    for i, p in enumerate(data, start=2):  # start=2 porque la fila 1 es encabezado
        if p["Nombre"] == nombre:
            polizas_ws.append_row([p["Nombre"], p["Correo"], p["Teléfono"], p["Producto"]])
            prospectos_ws.delete_rows(i)
            return True
    return False

def agregar_poliza(nombre, correo, telefono, producto):
    polizas_ws.append_row([nombre, correo, telefono, producto])

# ============================================================
# INTERFAZ STREAMLIT
# ============================================================
st.title("📋 Gestor de Prospectos y Pólizas")
menu = st.sidebar.radio("Menú", ["Agregar Prospecto", "Convertir a Póliza", "Agregar Póliza", "Ver Datos"])

if menu == "Agregar Prospecto":
    st.subheader("Agregar nuevo prospecto")
    nombre = st.text_input("Nombre")
    correo = st.text_input("Correo")
    telefono = st.text_input("Teléfono")
    producto = st.selectbox("Producto", ["Auto", "Vida", "Gastos Médicos", "Hogar"])
    if st.button("Guardar Prospecto"):
        if nombre and correo:
            agregar_prospecto(nombre, correo, telefono, producto)
            st.success(f"✅ Prospecto '{nombre}' agregado exitosamente.")
        else:
            st.warning("Por favor completa al menos nombre y correo.")

elif menu == "Convertir a Póliza":
    st.subheader("Convertir prospecto en póliza")
    data = prospectos_ws.get_all_records()
    if data:
        nombres = [p["Nombre"] for p in data]
        seleccionado = st.selectbox("Selecciona un prospecto", nombres)
        if st.button("Convertir"):
            if convertir_a_poliza(seleccionado):
                st.success(f"✅ Prospecto '{seleccionado}' convertido en póliza.")
            else:
                st.error("❌ No se encontró el prospecto.")
    else:
        st.info("No hay prospectos disponibles.")

elif menu == "Agregar Póliza":
    st.subheader("Agregar póliza directamente")
    nombre = st.text_input("Nombre")
    correo = st.text_input("Correo")
    telefono = st.text_input("Teléfono")
    producto = st.selectbox("Producto", ["Auto", "Vida", "Gastos Médicos", "Hogar"])
    if st.button("Guardar Póliza"):
        if nombre and correo:
            agregar_poliza(nombre, correo, telefono, producto)
            st.success(f"✅ Póliza '{nombre}' agregada exitosamente.")
        else:
            st.warning("Por favor completa al menos nombre y correo.")

elif menu == "Ver Datos":
    st.subheader("📊 Prospectos")
    prospectos = pd.DataFrame(prospectos_ws.get_all_records())
    st.dataframe(prospectos if not prospectos.empty else pd.DataFrame(columns=["Nombre", "Correo", "Teléfono", "Producto"]))

    st.subheader("📜 Pólizas")
    polizas = pd.DataFrame(polizas_ws.get_all_records())
    st.dataframe(polizas if not polizas.empty else pd.DataFrame(columns=["Nombre", "Correo", "Teléfono", "Producto"]))
