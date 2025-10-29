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

def obtener_polizas():
    """Obtiene todas las pólizas como lista de diccionarios"""
    try:
        return polizas_ws.get_all_records()
    except Exception as e:
        st.error(f"❌ Error al obtener pólizas: {str(e)}")
        return []

def obtener_ultimo_id_cliente():
    """Obtiene el último ID de cliente utilizado"""
    try:
        polizas = obtener_polizas()
        if not polizas:
            return 0
        
        ids_clientes = []
        for poliza in polizas:
            id_cliente = poliza.get("No. Cliente", "")
            if id_cliente and str(id_cliente).isdigit():
                ids_clientes.append(int(id_cliente))
        
        return max(ids_clientes) if ids_clientes else 0
    except Exception as e:
        st.error(f"❌ Error al obtener último ID: {str(e)}")
        return 0

def generar_nuevo_id_cliente():
    """Genera un nuevo ID de cliente automáticamente"""
    ultimo_id = obtener_ultimo_id_cliente()
    return ultimo_id + 1

def obtener_clientes_unicos():
    """Obtiene lista de clientes únicos para el dropdown"""
    try:
        polizas = obtener_polizas()
        if not polizas:
            return []
        
        clientes = {}
        for poliza in polizas:
            contratante = poliza.get("CONTRATANTE", "")
            id_cliente = poliza.get("No. Cliente", "")
            if contratante:
                clientes[contratante] = id_cliente
        
        # Ordenar alfabéticamente por nombre
        return sorted(clientes.keys())
    except Exception as e:
        st.error(f"❌ Error al obtener clientes: {str(e)}")
        return []

def buscar_por_nombre_cliente(nombre_cliente):
    """Busca pólizas por nombre del cliente"""
    try:
        polizas = obtener_polizas()
        resultados = [p for p in polizas if p.get("CONTRATANTE", "") == nombre_cliente]
        return resultados
    except Exception as e:
        st.error(f"❌ Error al buscar pólizas: {str(e)}")
        return []

def agregar_poliza(datos):
    """Agrega una nueva póliza a la hoja"""
    try:
        polizas_ws.append_row(datos)
        return True
    except Exception as e:
        st.error(f"❌ Error al agregar póliza: {str(e)}")
        return False

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
# FUNCIONES PARA MANEJO DE FECHAS
# ============================================================
def crear_campo_fecha(label, key, valor_default=None):
    """Crea un campo de fecha que permite años anteriores a 2015"""
    st.write(f"**{label}**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        dia = st.number_input(f"Día {label}", min_value=1, max_value=31, value=1, key=f"dia_{key}")
    with col2:
        mes = st.selectbox(f"Mes {label}", 
                          options=list(range(1, 13)),
                          format_func=lambda x: ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                                               "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][x-1],
                          key=f"mes_{key}")
    with col3:
        # Permitir años desde 1900 hasta el año actual + 10
        año_actual = datetime.now().year
        año = st.number_input(f"Año {label}", min_value=1900, max_value=año_actual + 10, value=1980, key=f"año_{key}")
    
    try:
        fecha = datetime(año, mes, dia).date()
        return fecha
    except ValueError:
        st.error(f"❌ Fecha inválida para {label}")
        return None

def crear_campo_fecha_simple(label, key, valor_default=None):
    """Alternativa más simple usando text_input para fecha"""
    if valor_default is None:
        valor_default = "01/01/1980"
    
    fecha_texto = st.text_input(
        label, 
        value=valor_default,
        placeholder="DD/MM/AAAA",
        key=key,
        help="Formato: DD/MM/AAAA (por ejemplo: 15/03/1975)"
    )
    
    # Validar formato de fecha
    if fecha_texto:
        try:
            fecha = datetime.strptime(fecha_texto, "%d/%m/%Y").date()
            return fecha
        except ValueError:
            st.error(f"❌ Formato de fecha incorrecto para {label}. Use DD/MM/AAAA")
            return None
    return None

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
    
    # Opción para elegir el tipo de entrada de fecha
    metodo_fecha = st.radio("Método para ingresar fechas:", 
                           ["📅 Selectores individuales (Día/Mes/Año)", "⌨️ Texto (DD/MM/AAAA)"],
                           key="metodo_fecha")
    
    with st.form("poliza_form", clear_on_submit=True):
        st.subheader("Información Básica")
        col1, col2 = st.columns(2)
        
        with col1:
            # ID de cliente generado automáticamente
            nuevo_id = generar_nuevo_id_cliente()
            st.text_input("No. Cliente *", value=str(nuevo_id), key="no_cliente_auto", disabled=True)
            
            contratante = st.text_input("CONTRATANTE *")
            asegurado = st.text_input("ASEGURADO *")
            beneficiario = st.text_input("BENEFICIARIO")
            
            # Campos de fecha de nacimiento según el método seleccionado
            if metodo_fecha == "📅 Selectores individuales (Día/Mes/Año)":
                st.write("FECHA DE NAC CONTRATANTE")
                fecha_nac_contratante = crear_campo_fecha("Nacimiento Contratante", "nac_cont")
                
                st.write("FECHA DE NAC ASEGURADO")
                fecha_nac_asegurado = crear_campo_fecha("Nacimiento Asegurado", "nac_aseg")
            else:
                fecha_nac_contratante = crear_campo_fecha_simple("FECHA DE NAC CONTRATANTE", "nac_cont_text")
                fecha_nac_asegurado = crear_campo_fecha_simple("FECHA DE NAC ASEGURADO", "nac_aseg_text")
            
            estado_civil = st.selectbox("ESTADO CIVIL", ["", "Soltero", "Casado", "Divorciado", "Viudo", "Unión Libre"])
        
        with col2:
            no_poliza = st.text_input("No. POLIZA *")
            
            # Fechas de vigencia según el método seleccionado
            if metodo_fecha == "📅 Selectores individuales (Día/Mes/Año)":
                st.write("INICIO DE VIGENCIA *")
                inicio_vigencia = crear_campo_fecha("Inicio Vigencia", "inicio_vig")
                
                st.write("FIN DE VIGENCIA *")
                fin_vigencia = crear_campo_fecha("Fin Vigencia", "fin_vig")
            else:
                inicio_vigencia = crear_campo_fecha_simple("INICIO DE VIGENCIA *", "inicio_vig_text", "01/01/2024")
                fin_vigencia = crear_campo_fecha_simple("FIN DE VIGENCIA *", "fin_vig_text", "31/12/2024")
            
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
            campos_faltantes = []
            if not contratante: campos_faltantes.append("CONTRATANTE")
            if not asegurado: campos_faltantes.append("ASEGURADO")
            if not no_poliza: campos_faltantes.append("No. POLIZA")
            if not inicio_vigencia: campos_faltantes.append("INICIO DE VIGENCIA")
            if not fin_vigencia: campos_faltantes.append("FIN DE VIGENCIA")
            
            if campos_faltantes:
                st.error(f"❌ Campos obligatorios faltantes: {', '.join(campos_faltantes)}")
            else:
                # Preparar datos para guardar
                datos_poliza = [
                    str(nuevo_id),  # ID generado automáticamente
                    contratante,
                    asegurado,
                    beneficiario,
                    fecha_nac_contratante.strftime("%d/%m/%Y") if fecha_nac_contratante else "",
                    fecha_nac_asegurado.strftime("%d/%m/%Y") if fecha_nac_asegurado else "",
                    estado_civil,
                    no_poliza,
                    inicio_vigencia.strftime("%d/%m/%Y") if inicio_vigencia else "",
                    fin_vigencia.strftime("%d/%m/%Y") if fin_vigencia else "",
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
                    st.success(f"✅ Póliza {no_poliza} guardada exitosamente para el cliente {contratante} (ID: {nuevo_id})!")
                    st.balloons()

# ============================================================
# 2. CONSULTAR PÓLIZAS POR CLIENTE
# ============================================================
elif menu == "🔍 Consultar Pólizas por Cliente":
    st.header("🔍 Consultar Pólizas por Cliente")
    
    # Obtener lista de clientes únicos para el dropdown
    with st.spinner("Cargando lista de clientes..."):
        clientes = obtener_clientes_unicos()
    
    if not clientes:
        st.info("ℹ️ No hay clientes registrados en el sistema")
    else:
        col1, col2 = st.columns([1, 3])
        
        with col1:
            cliente_seleccionado = st.selectbox(
                "Selecciona un cliente:",
                options=clientes,
                key="select_cliente"
            )
            buscar_btn = st.button("🔍 Buscar Pólizas")
        
        if buscar_btn and cliente_seleccionado:
            with st.spinner("Buscando pólizas..."):
                resultados = buscar_por_nombre_cliente(cliente_seleccionado)
                
            if resultados:
                st.success(f"✅ Se encontraron {len(resultados)} póliza(s) para el cliente {cliente_seleccionado}")
                
                # Mostrar resumen
                df_resultados = pd.DataFrame(resultados)
                
                # Columnas importantes para mostrar
                columnas_importantes = ["No. Cliente", "No. POLIZA", "PRODUCTO", "INICIO DE VIGENCIA", "FIN DE VIGENCIA", "PRIMA ANUAL", "ASEGURADORA"]
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
                    file_name=f"polizas_cliente_{cliente_seleccionado.replace(' ', '_')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning(f"ℹ️ No se encontraron pólizas para el cliente {cliente_seleccionado}")

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
- **Data Entry**: El ID de cliente se genera automáticamente
- **Consultar**: Busca por nombre del cliente en lista desplegable  
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
        
        # Mostrar último ID utilizado
        ultimo_id = obtener_ultimo_id_cliente()
        st.sidebar.write(f"**Último ID utilizado:** {ultimo_id}")
except:
    pass
