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

def init_google_sheets():
    """Inicializa la conexión con Google Sheets"""
    try:
        # Verificar que el secret existe
        if 'google_service_account' not in st.secrets:
            st.error("❌ No se encontró 'google_service_account' en los secrets de Streamlit")
            return None
        
        # Cargamos las credenciales directamente desde los secrets
        creds = Credentials.from_service_account_info(
            st.secrets["google_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets", 
                   "https://www.googleapis.com/auth/drive"]
        )
        
        # Autenticamos cliente de Google Sheets
        client = gspread.authorize(creds)
        return client
        
    except Exception as e:
        st.error(f"❌ Error al autenticar con Google Sheets: {str(e)}")
        return None

# Inicializar cliente
client = init_google_sheets()

if client is None:
    st.stop()

# ============================================================
# CONECTAR A TU GOOGLE SHEET
# ============================================================
SPREADSHEET_NAME = "base_poliza"

try:
    sheet = client.open(SPREADSHEET_NAME)
    st.sidebar.success("✅ Conectado a Google Sheets")
except gspread.SpreadsheetNotFound:
    st.error(f"❌ No se encontró el archivo '{SPREADSHEET_NAME}' en tu cuenta de Google.")
    st.stop()
except Exception as e:
    st.error(f"❌ Error al abrir la hoja de cálculo: {str(e)}")
    st.stop()

# ============================================================
# CREAR HOJAS SI NO EXISTEN
# ============================================================
def ensure_sheet_exists(sheet, title, headers):
    """Crea la hoja si no existe, con los encabezados dados."""
    try:
        worksheet = sheet.worksheet(title)
        # Verificar si la hoja tiene los encabezados correctos
        existing_headers = worksheet.row_values(1)
        if existing_headers != headers:
            worksheet.clear()
            worksheet.append_row(headers)
    except gspread.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=title, rows="100", cols=str(len(headers)))
        worksheet.append_row(headers)
    except Exception as e:
        st.error(f"❌ Error al crear/verificar la hoja {title}: {str(e)}")
        return None
    return worksheet

# Crear hojas con encabezados
prospectos_headers = ["Nombre", "Correo", "Teléfono", "Producto", "Fecha"]
polizas_headers = ["Nombre", "Correo", "Teléfono", "Producto", "Fecha"]

prospectos_ws = ensure_sheet_exists(sheet, "Prospectos", prospectos_headers)
polizas_ws = ensure_sheet_exists(sheet, "Polizas", polizas_headers)

if prospectos_ws is None or polizas_ws is None:
    st.error("❌ No se pudieron inicializar las hojas de trabajo")
    st.stop()

# ============================================================
# FUNCIONES DE APP
# ============================================================
import datetime

def agregar_prospecto(nombre, correo, telefono, producto):
    """Agrega un nuevo prospecto a la hoja"""
    try:
        fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prospectos_ws.append_row([nombre, correo, telefono, producto, fecha])
        return True
    except Exception as e:
        st.error(f"❌ Error al agregar prospecto: {str(e)}")
        return False

def obtener_prospectos():
    """Obtiene todos los prospectos como lista de diccionarios"""
    try:
        return prospectos_ws.get_all_records()
    except Exception as e:
        st.error(f"❌ Error al obtener prospectos: {str(e)}")
        return []

def convertir_a_poliza(nombre):
    """Convierte un prospecto en póliza"""
    try:
        data = obtener_prospectos()
        for i, p in enumerate(data, start=2):  # start=2 porque la fila 1 es encabezado
            if p["Nombre"] == nombre:
                fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Agregar a pólizas
                polizas_ws.append_row([p["Nombre"], p["Correo"], p["Teléfono"], p["Producto"], fecha])
                # Eliminar de prospectos
                prospectos_ws.delete_rows(i)
                return True
        return False
    except Exception as e:
        st.error(f"❌ Error al convertir a póliza: {str(e)}")
        return False

def agregar_poliza(nombre, correo, telefono, producto):
    """Agrega una póliza directamente"""
    try:
        fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        polizas_ws.append_row([nombre, correo, telefono, producto, fecha])
        return True
    except Exception as e:
        st.error(f"❌ Error al agregar póliza: {str(e)}")
        return False

def obtener_polizas():
    """Obtiene todas las pólizas como lista de diccionarios"""
    try:
        return polizas_ws.get_all_records()
    except Exception as e:
        st.error(f"❌ Error al obtener pólizas: {str(e)}")
        return []

# ============================================================
# INTERFAZ STREAMLIT
# ============================================================
st.title("📋 Gestor de Prospectos y Pólizas")
st.sidebar.title("Navegación")
menu = st.sidebar.radio("Menú", ["Agregar Prospecto", "Convertir a Póliza", "Agregar Póliza", "Ver Datos"])

if menu == "Agregar Prospecto":
    st.subheader("➕ Agregar nuevo prospecto")
    
    with st.form("prospecto_form"):
        nombre = st.text_input("Nombre *", placeholder="Ingresa el nombre completo")
        correo = st.text_input("Correo *", placeholder="ejemplo@correo.com")
        telefono = st.text_input("Teléfono", placeholder="+52 123 456 7890")
        producto = st.selectbox("Producto *", ["", "Auto", "Vida", "Gastos Médicos", "Hogar", "Otro"])
        
        submitted = st.form_submit_button("Guardar Prospecto")
        if submitted:
            if nombre.strip() and correo.strip() and producto:
                if agregar_prospecto(nombre, correo, telefono, producto):
                    st.success(f"✅ Prospecto '{nombre}' agregado exitosamente!")
                    st.balloons()
            else:
                st.warning("⚠️ Por favor completa los campos obligatorios (*)")

elif menu == "Convertir a Póliza":
    st.subheader("🔄 Convertir prospecto en póliza")
    
    data = obtener_prospectos()
    if data:
        nombres = [p["Nombre"] for p in data if p["Nombre"]]
        if nombres:
            seleccionado = st.selectbox("Selecciona un prospecto", nombres)
            if st.button("Convertir a Póliza"):
                if convertir_a_poliza(seleccionado):
                    st.success(f"✅ Prospecto '{seleccionado}' convertido en póliza exitosamente!")
                    st.rerun()
                else:
                    st.error("❌ No se pudo convertir el prospecto")
        else:
            st.info("ℹ️ No hay prospectos con nombre válido")
    else:
        st.info("ℹ️ No hay prospectos disponibles para convertir")

elif menu == "Agregar Póliza":
    st.subheader("📄 Agregar póliza directamente")
    
    with st.form("poliza_form"):
        nombre = st.text_input("Nombre *", placeholder="Ingresa el nombre completo")
        correo = st.text_input("Correo *", placeholder="ejemplo@correo.com")
        telefono = st.text_input("Teléfono", placeholder="+52 123 456 7890")
        producto = st.selectbox("Producto *", ["", "Auto", "Vida", "Gastos Médicos", "Hogar", "Otro"])
        
        submitted = st.form_submit_button("Guardar Póliza")
        if submitted:
            if nombre.strip() and correo.strip() and producto:
                if agregar_poliza(nombre, correo, telefono, producto):
                    st.success(f"✅ Póliza '{nombre}' agregada exitosamente!")
                    st.balloons()
            else:
                st.warning("⚠️ Por favor completa los campos obligatorios (*)")

elif menu == "Ver Datos":
    st.subheader("📊 Datos Guardados")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**👥 Prospectos**")
        prospectos = obtener_prospectos()
        if prospectos:
            df_prospectos = pd.DataFrame(prospectos)
            st.dataframe(df_prospectos, use_container_width=True)
            st.metric("Total Prospectos", len(prospectos))
        else:
            st.info("ℹ️ No hay prospectos registrados")
    
    with col2:
        st.write("**📑 Pólizas**")
        polizas = obtener_polizas()
        if polizas:
            df_polizas = pd.DataFrame(polizas)
            st.dataframe(df_polizas, use_container_width=True)
            st.metric("Total Pólizas", len(polizas))
        else:
            st.info("ℹ️ No hay pólizas registradas")

# ============================================================
# INFORMACIÓN ADICIONAL
# ============================================================
st.sidebar.markdown("---")
st.sidebar.info("""
**Configuración requerida:**
1. Google Service Account en Secrets
2. Hoja de cálculo 'base_poliza' en Google Drive
3. Compartir la hoja con el email del service account
""")
