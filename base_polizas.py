import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import ssl
from datetime import datetime, timedelta
import io

# ============================================================
# CONFIGURACIÓN INICIAL
# ============================================================
ssl._create_default_https_context = ssl._create_unverified_context

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Gestión de Pólizas",
    page_icon="📋",
    layout="wide"
)

# ============================================================
# CONFIGURACIÓN DE GOOGLE SHEETS
# ============================================================
def init_google_sheets():
    """Inicializa la conexión con Google Sheets"""
    try:
        if 'google_service_account' not in st.secrets:
            st.error("❌ No se encontró 'google_service_account' en los secrets de Streamlit")
            return None
        
        creds = Credentials.from_service_account_info(
            st.secrets["google_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets", 
                   "https://www.googleapis.com/auth/drive"]
        )
        
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
# CONFIGURACIÓN DE LA HOJA DE CÁLCULO
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
# DEFINICIÓN DE CAMPOS
# ============================================================
CAMPOS_POLIZA = [
    "No. Cliente", "CONTRATANTE", "ASEGURADO", "BENEFICIARIO",
    "FECHA DE NAC CONTRATANTE", "FECHA DE NAC ASEGURADO", "ESTADO CIVIL",
    "No. POLIZA", "INICIO DE VIGENCIA", "FIN DE VIGENCIA", "FORMA DE PAGO",
    "FRECUENCIA DE PAGO", "PRIMA ANUAL", "PRODUCTO", "No Serie Auto",
    "ASEGURADORA", "DIRECCIÓN", "TELEFONO", "EMAIL", "NOTAS", "DESCRIPCION AUTO"
]

# ============================================================
# FUNCIONES PRINCIPALES
# ============================================================
def ensure_sheet_exists(sheet, title, headers):
    """Crea la hoja si no existe, con los encabezados dados."""
    try:
        worksheet = sheet.worksheet(title)
        # Verificar encabezados existentes
        existing_headers = worksheet.row_values(1)
        if existing_headers != headers:
            st.warning(f"⚠️ Los encabezados en '{title}' no coinciden. Se usarán los existentes.")
    except gspread.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=title, rows="1000", cols=str(len(headers)))
        worksheet.append_row(headers)
    except Exception as e:
        st.error(f"❌ Error al crear/verificar la hoja {title}: {str(e)}")
        return None
    return worksheet

def agregar_poliza(datos):
    """Agrega una nueva póliza a la hoja"""
    try:
        polizas_ws.append_row(datos)
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

def buscar_por_cliente(numero_cliente):
    """Busca pólizas por número de cliente"""
    try:
        polizas = obtener_polizas()
        resultados = [p for p in polizas if str(p.get("No. Cliente", "")) == str(numero_cliente)]
        return resultados
    except Exception as e:
        st.error(f"❌ Error al buscar pólizas: {str(e)}")
        return []

def obtener_polizas_proximas_vencer(dias=30):
    """Obtiene pólizas que vencen en los próximos N días"""
    try:
        polizas = obtener_polizas()
        hoy = datetime.now().date()
        fecha_limite = hoy + timedelta(days=dias)
        
        polizas_proximas = []
        
        for poliza in polizas:
            fecha_fin = poliza.get("FIN DE VIGENCIA", "")
            if fecha_fin:
                try:
                    # Intentar diferentes formatos de fecha
                    if isinstance(fecha_fin, str):
                        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']:
                            try:
                                fecha_fin_dt = datetime.strptime(fecha_fin, fmt).date()
                                break
                            except ValueError:
                                continue
                        else:
                            continue
                    else:
                        continue
                    
                    if hoy <= fecha_fin_dt <= fecha_limite:
                        polizas_proximas.append(poliza)
                        
                except Exception:
                    continue
        
        return polizas_proximas
    except Exception as e:
        st.error(f"❌ Error al obtener pólizas próximas a vencer: {str(e)}")
        return []

# ============================================================
# INICIALIZAR HOJA DE PÓLIZAS
# ============================================================
polizas_ws = ensure_sheet_exists(sheet, "Polizas", CAMPOS_POLIZA)
if polizas_ws is None:
    st.error("❌ No se pudo inicializar la hoja de pólizas")
    st.stop()

# ============================================================
# INTERFAZ PRINCIPAL
# ============================================================
st.title("🏢 Sistema de Gestión de Pólizas")
st.markdown("---")

# Menú principal
menu = st.sidebar.radio("Navegación", [
    "📝 Data Entry - Nueva Póliza", 
    "🔍 Consultar Pólizas por Cliente", 
    "⏳ Pólizas Próximas a Vencer",
    "📊 Ver Todas las Pólizas"
])

# ============================================================
# 1. DATA ENTRY - NUEVA PÓLIZA
# ============================================================
if menu == "📝 Data Entry - Nueva Póliza":
    st.header("📝 Ingresar Nueva Póliza")
    
    with st.form("poliza_form", clear_on_submit=True):
        st.subheader("Información Básica")
        col1, col2 = st.columns(2)
        
        with col1:
            no_cliente = st.text_input("No. Cliente *", help="ID único del cliente")
            contratante = st.text_input("CONTRATANTE *")
            asegurado = st.text_input("ASEGURADO *")
            beneficiario = st.text_input("BENEFICIARIO")
            fecha_nac_contratante = st.date_input("FECHA DE NAC CONTRATANTE")
            fecha_nac_asegurado = st.date_input("FECHA DE NAC ASEGURADO")
            estado_civil = st.selectbox("ESTADO CIVIL", ["", "Soltero", "Casado", "Divorciado", "Viudo", "Unión Libre"])
        
        with col2:
            no_poliza = st.text_input("No. POLIZA *")
            inicio_vigencia = st.date_input("INICIO DE VIGENCIA *")
            fin_vigencia = st.date_input("FIN DE VIGENCIA *")
            forma_pago = st.selectbox("FORMA DE PAGO", ["", "Efectivo", "Tarjeta", "Transferencia", "Débito Automático"])
            frecuencia_pago = st.selectbox("FRECUENCIA DE PAGO", ["", "Anual", "Semestral", "Trimestral", "Mensual"])
            prima_anual = st.number_input("PRIMA ANUAL", min_value=0.0, format="%.2f")
            producto = st.text_input("PRODUCTO")
        
        st.subheader("Información Adicional")
        col3, col4 = st.columns(2)
        
        with col3:
            no_serie_auto = st.text_input("No Serie Auto")
            aseguradora = st.text_input("ASEGURADORA")
            direccion = st.text_area("DIRECCIÓN")
        
        with col4:
            telefono = st.text_input("TELEFONO")
            email = st.text_input("EMAIL")
            notas = st.text_area("NOTAS")
            descripcion_auto = st.text_area("DESCRIPCION AUTO")
        
        submitted = st.form_submit_button("💾 Guardar Póliza")
        
        if submitted:
            # Validar campos obligatorios
            if not no_cliente or not contratante or not asegurado or not no_poliza:
                st.error("❌ Por favor completa los campos obligatorios (*)")
            else:
                # Preparar datos para guardar
                datos_poliza = [
                    no_cliente,
                    contratante,
                    asegurado,
                    beneficiario,
                    fecha_nac_contratante.strftime("%Y-%m-%d") if fecha_nac_contratante else "",
                    fecha_nac_asegurado.strftime("%Y-%m-%d") if fecha_nac_asegurado else "",
                    estado_civil,
                    no_poliza,
                    inicio_vigencia.strftime("%Y-%m-%d") if inicio_vigencia else "",
                    fin_vigencia.strftime("%Y-%m-%d") if fin_vigencia else "",
                    forma_pago,
                    frecuencia_pago,
                    prima_anual,
                    producto,
                    no_serie_auto,
                    aseguradora,
                    direccion,
                    telefono,
                    email,
                    notas,
                    descripcion_auto
                ]
                
                if agregar_poliza(datos_poliza):
                    st.success(f"✅ Póliza {no_poliza} guardada exitosamente para el cliente {no_cliente}!")
                    st.balloons()

# ============================================================
# 2. CONSULTAR PÓLIZAS POR CLIENTE
# ============================================================
elif menu == "🔍 Consultar Pólizas por Cliente":
    st.header("🔍 Consultar Pólizas por Cliente")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        no_cliente_buscar = st.text_input("Ingresa el No. Cliente")
        buscar_btn = st.button("🔍 Buscar Pólizas")
    
    if buscar_btn and no_cliente_buscar:
        with st.spinner("Buscando pólizas..."):
            resultados = buscar_por_cliente(no_cliente_buscar)
            
        if resultados:
            st.success(f"✅ Se encontraron {len(resultados)} póliza(s) para el cliente {no_cliente_buscar}")
            
            # Mostrar resumen
            df_resultados = pd.DataFrame(resultados)
            
            # Columnas importantes para mostrar
            columnas_importantes = ["No. POLIZA", "PRODUCTO", "INICIO DE VIGENCIA", "FIN DE VIGENCIA", "PRIMA ANUAL", "ASEGURADORA"]
            columnas_disponibles = [col for col in columnas_importantes if col in df_resultados.columns]
            
            st.dataframe(df_resultados[columnas_disponibles], use_container_width=True)
            
            # Opción para ver todos los detalles
            with st.expander("📋 Ver detalles completos de todas las pólizas"):
                st.dataframe(df_resultados, use_container_width=True)
                
            # Descargar resultados
            csv = df_resultados.to_csv(index=False, encoding='utf-8')
            st.download_button(
                label="📥 Descargar resultados en CSV",
                data=csv,
                file_name=f"polizas_cliente_{no_cliente_buscar}.csv",
                mime="text/csv"
            )
        else:
            st.warning(f"ℹ️ No se encontraron pólizas para el cliente {no_cliente_buscar}")

# ============================================================
# 3. PÓLIZAS PRÓXIMAS A VENCER
# ============================================================
elif menu == "⏳ Pólizas Próximas a Vencer":
    st.header("⏳ Pólizas Próximas a Vencer (Próximos 30 días)")
    
    with st.spinner("Buscando pólizas próximas a vencer..."):
        polizas_proximas = obtener_polizas_proximas_vencer(30)
    
    if polizas_proximas:
        st.success(f"✅ Se encontraron {len(polizas_proximas)} póliza(s) que vencen en los próximos 30 días")
        
        df_proximas = pd.DataFrame(polizas_proximas)
        
        # Columnas relevantes para vencimientos
        columnas_vencimiento = ["No. Cliente", "CONTRATANTE", "No. POLIZA", "PRODUCTO", "FIN DE VIGENCIA", "PRIMA ANUAL", "TELEFONO", "EMAIL"]
        columnas_disponibles = [col for col in columnas_vencimiento if col in df_proximas.columns]
        
        st.dataframe(df_proximas[columnas_disponibles], use_container_width=True)
        
        with st.expander("📋 Ver todos los detalles"):
            st.dataframe(df_proximas, use_container_width=True)
        
        # Estadísticas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Pólizas a Vencer", len(polizas_proximas))
        with col2:
            if 'PRIMA ANUAL' in df_proximas.columns:
                prima_total = df_proximas['PRIMA ANUAL'].sum()
                st.metric("Prima Total", f"${prima_total:,.2f}")
        
        # Descargar reporte
        csv = df_proximas.to_csv(index=False, encoding='utf-8')
        st.download_button(
            label="📥 Descargar Reporte de Vencimientos",
            data=csv,
            file_name=f"polizas_proximas_vencer_{datetime.now().strftime('%Y-%m-%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("ℹ️ No hay pólizas que venzan en los próximos 30 días")

# ============================================================
# 4. VER TODAS LAS PÓLIZAS
# ============================================================
elif menu == "📊 Ver Todas las Pólizas":
    st.header("📊 Todas las Pólizas Registradas")
    
    with st.spinner("Cargando pólizas..."):
        todas_polizas = obtener_polizas()
    
    if todas_polizas:
        df_todas = pd.DataFrame(todas_polizas)
        
        # Filtros
        col1, col2, col3 = st.columns(3)
        with col1:
            filtro_producto = st.selectbox("Filtrar por Producto", [""] + sorted(df_todas['PRODUCTO'].unique() if 'PRODUCTO' in df_todas.columns else []))
        with col2:
            filtro_aseguradora = st.selectbox("Filtrar por Aseguradora", [""] + sorted(df_todas['ASEGURADORA'].unique() if 'ASEGURADORA' in df_todas.columns else []))
        
        # Aplicar filtros
        if filtro_producto:
            df_todas = df_todas[df_todas['PRODUCTO'] == filtro_producto]
        if filtro_aseguradora:
            df_todas = df_todas[df_todas['ASEGURADORA'] == filtro_aseguradora]
        
        # Mostrar datos
        st.dataframe(df_todas, use_container_width=True)
        
        # Estadísticas
        st.subheader("📈 Estadísticas")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Pólizas", len(df_todas))
        with col2:
            st.metric("Clientes Únicos", df_todas['No. Cliente'].nunique() if 'No. Cliente' in df_todas.columns else 0)
        with col3:
            if 'PRIMA ANUAL' in df_todas.columns:
                st.metric("Prima Anual Total", f"${df_todas['PRIMA ANUAL'].sum():,.2f}")
        with col4:
            if 'PRODUCTO' in df_todas.columns:
                st.metric("Productos Diferentes", df_todas['PRODUCTO'].nunique())
        
        # Descargar datos completos
        csv = df_todas.to_csv(index=False, encoding='utf-8')
        st.download_button(
            label="📥 Descargar Base Completa en CSV",
            data=csv,
            file_name=f"base_polizas_completa_{datetime.now().strftime('%Y-%m-%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("ℹ️ No hay pólizas registradas en el sistema")

# ============================================================
# INFORMACIÓN ADICIONAL EN SIDEBAR
# ============================================================
st.sidebar.markdown("---")
st.sidebar.info("""
**💡 Instrucciones:**
- **Data Entry**: Completa todos los campos para nueva póliza
- **Consultar**: Busca por No. Cliente para ver todas sus pólizas  
- **Vencimientos**: Revisa pólizas que vencerán pronto
- **Ver Todo**: Explora y filtra toda la base de datos
""")

# Mostrar estadísticas rápidas en sidebar
try:
    todas_polizas = obtener_polizas()
    if todas_polizas:
        df_temp = pd.DataFrame(todas_polizas)
        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 Resumen")
        st.sidebar.write(f"**Pólizas totales:** {len(df_temp)}")
        st.sidebar.write(f"**Clientes únicos:** {df_temp['No. Cliente'].nunique() if 'No. Cliente' in df_temp.columns else 'N/A'}")
        
        # Pólizas próximas a vencer
        proximas = obtener_polizas_proximas_vencer(30)
        st.sidebar.write(f"**Próximas a vencer (30 días):** {len(proximas)}")
except:
    pass
