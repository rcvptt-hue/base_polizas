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
    
    # Inicializar estado de sesión para el formulario
    if 'form_submitted' not in st.session_state:
        st.session_state.form_submitted = False
    
    # ID de cliente generado automáticamente
    nuevo_id = generar_nuevo_id_cliente()
    
    # Crear contenedor para el formulario
    form_container = st.container()
    
    with form_container:
        st.subheader("Información Básica")
        col1, col2 = st.columns(2)
        
        with col1:
            st.text_input("No. Cliente *", value=str(nuevo_id), key="no_cliente_auto", disabled=True)
            contratante = st.text_input("CONTRATANTE *", key="contratante_input")
            asegurado = st.text_input("ASEGURADO *", key="asegurado_input")
            beneficiario = st.text_input("BENEFICIARIO", key="beneficiario_input")
            
            # Campos de fecha usando texto (más flexible para años anteriores)
            fecha_nac_contratante = st.text_input(
                "FECHA DE NAC CONTRATANTE (DD/MM/AAAA)", 
                placeholder="DD/MM/AAAA",
                key="fecha_nac_contratante_input"
            )
            
            fecha_nac_asegurado = st.text_input(
                "FECHA DE NAC ASEGURADO (DD/MM/AAAA)", 
                placeholder="DD/MM/AAAA", 
                key="fecha_nac_asegurado_input"
            )
            
            estado_civil = st.selectbox(
                "ESTADO CIVIL", 
                ["", "Soltero", "Casado", "Divorciado", "Viudo", "Unión Libre"],
                key="estado_civil_select"
            )
        
        with col2:
            no_poliza = st.text_input("No. POLIZA *", key="no_poliza_input")
            
            inicio_vigencia = st.text_input(
                "INICIO DE VIGENCIA * (DD/MM/AAAA)", 
                placeholder="DD/MM/AAAA",
                key="inicio_vigencia_input"
            )
            
            fin_vigencia = st.text_input(
                "FIN DE VIGENCIA * (DD/MM/AAAA)", 
                placeholder="DD/MM/AAAA",
                key="fin_vigencia_input"
            )
            
            forma_pago = st.selectbox(
                "FORMA DE PAGO", 
                ["", "Efectivo", "Tarjeta", "Transferencia", "Débito Automático"],
                key="forma_pago_select"
            )
            
            frecuencia_pago = st.selectbox(
                "FRECUENCIA DE PAGO", 
                ["", "Anual", "Semestral", "Trimestral", "Mensual"],
                key="frecuencia_pago_select"
            )
            
            prima_anual = st.number_input(
                "PRIMA ANUAL", 
                min_value=0.0, 
                format="%.2f",
                key="prima_anual_input"
            )
            
            producto = st.text_input("PRODUCTO", key="producto_input")
        
        st.subheader("Información Adicional")
        col3, col4 = st.columns(2)
        
        with col3:
            no_serie_auto = st.text_input("No Serie Auto", key="no_serie_auto_input")
            aseguradora = st.text_input("ASEGURADORA", key="aseguradora_input")
            direccion = st.text_area("DIRECCIÓN", key="direccion_input")
        
        with col4:
            telefono = st.text_input("TELEFONO", key="telefono_input")
            email = st.text_input("EMAIL", key="email_input")
            notas = st.text_area("NOTAS", key="notas_input")
            descripcion_auto = st.text_area("DESCRIPCION AUTO", key="descripcion_auto_input")
    
    # Botón fuera del contenedor del formulario para evitar envío con Enter
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    
    with col_btn2:
        guardar_button = st.button("💾 Guardar Póliza", use_container_width=True, type="primary")
    
    if guardar_button:
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
                str(nuevo_id),
                contratante,
                asegurado,
                beneficiario,
                fecha_nac_contratante,
                fecha_nac_asegurado,
                estado_civil,
                no_poliza,
                inicio_vigencia,
                fin_vigencia,
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
                
                # Limpiar el formulario usando session state
                for key in st.session_state.keys():
                    if key.endswith('_input') or key.endswith('_select'):
                        if key not in ['no_cliente_auto']:  # No limpiar el ID
                            st.session_state[key] = ""
                
                # Limpiar campos específicos
                st.session_state.prima_anual_input = 0.0
                st.session_state.estado_civil_select = ""
                st.session_state.forma_pago_select = ""
                st.session_state.frecuencia_pago_select = ""
                
                # Forzar rerun para actualizar la interfaz
                st.rerun()

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
                
                # ============================================================
                # NUEVA FUNCIONALIDAD: DUPLICAR PÓLIZA
                # ============================================================
                st.markdown("---")
                st.subheader("🔄 Duplicar Póliza")
                
                # Seleccionar póliza a duplicar
                polizas_para_duplicar = [f"{p['No. POLIZA']} - {p['PRODUCTO']} (Vence: {p.get('FIN DE VIGENCIA', 'N/A')})" 
                                       for p in resultados]
                
                if polizas_para_duplicar:
                    poliza_seleccionada = st.selectbox(
                        "Selecciona la póliza a duplicar:",
                        options=polizas_para_duplicar,
                        key="select_poliza_duplicar"
                    )
                    
                    if poliza_seleccionada:
                        # Encontrar la póliza original
                        poliza_original = None
                        for p in resultados:
                            if f"{p['No. POLIZA']} - {p['PRODUCTO']} (Vence: {p.get('FIN DE VIGENCIA', 'N/A')})" == poliza_seleccionada:
                                poliza_original = p
                                break
                        
                        if poliza_original:
                            # Formulario para duplicar póliza
                            with st.form("form_duplicar_poliza"):
                                st.write("**Complete los nuevos datos para la póliza duplicada:**")
                                
                                col_dup1, col_dup2 = st.columns(2)
                                
                                with col_dup1:
                                    nuevo_no_poliza = st.text_input(
                                        "Nuevo No. POLIZA *",
                                        value="",
                                        key="nuevo_no_poliza"
                                    )
                                    nuevo_inicio_vigencia = st.text_input(
                                        "Nuevo INICIO DE VIGENCIA * (DD/MM/AAAA)",
                                        placeholder="DD/MM/AAAA",
                                        key="nuevo_inicio_vigencia"
                                    )
                                    nuevo_fin_vigencia = st.text_input(
                                        "Nuevo FIN DE VIGENCIA * (DD/MM/AAAA)",
                                        placeholder="DD/MM/AAAA",
                                        key="nuevo_fin_vigencia"
                                    )
                                    nueva_prima_anual = st.number_input(
                                        "Nueva PRIMA ANUAL",
                                        value=float(poliza_original.get('PRIMA ANUAL', 0)),
                                        min_value=0.0,
                                        format="%.2f",
                                        key="nueva_prima_anual"
                                    )
                                
                                with col_dup2:
                                    nuevo_producto = st.text_input(
                                        "PRODUCTO",
                                        value=poliza_original.get('PRODUCTO', ''),
                                        key="nuevo_producto"
                                    )
                                    nueva_aseguradora = st.text_input(
                                        "ASEGURADORA",
                                        value=poliza_original.get('ASEGURADORA', ''),
                                        key="nueva_aseguradora"
                                    )
                                    nuevas_notas = st.text_area(
                                        "NOTAS",
                                        value=poliza_original.get('NOTAS', ''),
                                        key="nuevas_notas"
                                    )
                                
                                # Botón para duplicar
                                duplicar_btn = st.form_submit_button("✅ Duplicar Póliza", type="primary")
                                
                                if duplicar_btn:
                                    # Validar campos obligatorios
                                    if not nuevo_no_poliza or not nuevo_inicio_vigencia or not nuevo_fin_vigencia:
                                        st.error("❌ Por favor complete los campos obligatorios: Nuevo No. POLIZA, INICIO DE VIGENCIA y FIN DE VIGENCIA")
                                    else:
                                        # Preparar datos de la nueva póliza
                                        nueva_poliza = [
                                            poliza_original.get('No. Cliente', ''),  # Mismo ID de cliente
                                            poliza_original.get('CONTRATANTE', ''),
                                            poliza_original.get('ASEGURADO', ''),
                                            poliza_original.get('BENEFICIARIO', ''),
                                            poliza_original.get('FECHA DE NAC CONTRATANTE', ''),
                                            poliza_original.get('FECHA DE NAC ASEGURADO', ''),
                                            poliza_original.get('ESTADO CIVIL', ''),
                                            nuevo_no_poliza,  # Nuevo número de póliza
                                            nuevo_inicio_vigencia,  # Nueva fecha de inicio
                                            nuevo_fin_vigencia,  # Nueva fecha de fin
                                            poliza_original.get('FORMA DE PAGO', ''),
                                            poliza_original.get('FRECUENCIA DE PAGO', ''),
                                            nueva_prima_anual,  # Prima puede ser modificada
                                            nuevo_producto,  # Producto puede ser modificado
                                            poliza_original.get('No Serie Auto', ''),
                                            nueva_aseguradora,  # Aseguradora puede ser modificada
                                            poliza_original.get('DIRECCIÓN', ''),
                                            poliza_original.get('TELEFONO', ''),
                                            poliza_original.get('EMAIL', ''),
                                            nuevas_notas,  # Notas pueden ser modificadas
                                            poliza_original.get('DESCRIPCION AUTO', '')
                                        ]
                                        
                                        if agregar_poliza(nueva_poliza):
                                            st.success(f"✅ Póliza duplicada exitosamente! Nueva póliza: {nuevo_no_poliza}")
                                            st.balloons()
                                            st.rerun()
                
                # Descargar resultados
                st.markdown("---")
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
- **Data Entry**: Completa los campos y haz clic en Guardar
- **Consultar**: Busca por nombre del cliente y duplica pólizas  
- **Vencimientos**: Revisa pólizas que vencerán pronto
- **Ver Todo**: Explora toda la base de datos
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

# ============================================================
# JAVASCRIPT PARA DESHABILITAR ENTER EN FORMULARIOS
# ============================================================
# Inyectar JavaScript para prevenir el envío del formulario con Enter
st.markdown("""
<script>
document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                return false;
            }
        });
    });
});
</script>
""", unsafe_allow_html=True)
