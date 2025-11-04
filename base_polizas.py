import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import ssl
from datetime import datetime, timedelta
import io
import time
from functools import lru_cache
import re
import uuid

# ============================================================
# CONFIGURACIÓN INICIAL
# ============================================================
ssl._create_default_https_context = ssl._create_unverified_context

st.set_page_config(
    page_title="Sistema de Gestión de Pólizas",
    page_icon="📋",
    layout="wide"
)

# ============================================================
# FUNCIÓN DE VALIDACIÓN DE FECHAS MEJORADA
# ============================================================
def validar_fecha(fecha_str, es_vigencia=False):
    """Valida que la fecha tenga formato dd/mm/yyyy y sea una fecha válida"""
    if not fecha_str or fecha_str.strip() == "":
        return True, ""  # Fecha vacía es válida (para campos no obligatorios)
    
    fecha_str = str(fecha_str).strip()
    
    # Patrón regex para formato dd/mm/yyyy
    patron = r'^\d{1,2}/\d{1,2}/\d{4}$'
    if not re.match(patron, fecha_str):
        return False, "Formato incorrecto. Use dd/mm/yyyy (ejemplo: 15/03/1990)"
    
    try:
        # Extraer día, mes y año
        dia, mes, anio = map(int, fecha_str.split('/'))
        
        # Validar que la fecha sea real
        datetime(anio, mes, dia)
        
        # Validaciones adicionales
        if es_vigencia:
            # Para vigencias, solo validamos formato y fecha real, sin límite de año
            if mes < 1 or mes > 12:
                return False, "Mes debe estar entre 1 y 12"
            
            if dia < 1 or dia > 31:
                return False, "Día debe estar entre 1 y 31"
        else:
            # Para fechas de nacimiento, mantenemos las validaciones originales
            if anio < 1900 or anio > datetime.now().year:
                return False, f"Año {anio} fuera de rango válido (1900-{datetime.now().year})"
            
            if mes < 1 or mes > 12:
                return False, "Mes debe estar entre 1 y 12"
            
            if dia < 1 or dia > 31:
                return False, "Día debe estar entre 1 y 31"
            
        return True, ""
        
    except ValueError as e:
        return False, "La fecha no es válida (ejemplo: 15/03/1990)"

# ============================================================
# INICIALIZACIÓN DEL ESTADO DEL FORMULARIO
# ============================================================
def inicializar_estado_formulario():
    """Inicializa el estado para mantener los datos del formulario"""
    if 'datos_formulario' not in st.session_state:
        st.session_state.datos_formulario = {}

# Llamar a la inicialización al inicio
inicializar_estado_formulario()

# ============================================================
# CONFIGURACIÓN DE GOOGLE SHEETS
# ============================================================
def init_google_sheets():
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

client = init_google_sheets()
if client is None:
    st.stop()

# ============================================================
# CONFIGURACIÓN DE LA HOJA DE CÁLCULO
# ============================================================
SPREADSHEET_NAME = "base_poliza"

@st.cache_resource(show_spinner=False)
def get_sheet_with_retry():
    max_retries = 3
    for attempt in range(max_retries):
        try:
            sheet = client.open(SPREADSHEET_NAME)
            return sheet
        except gspread.exceptions.APIError as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait_time = (2 ** attempt) + 2
                time.sleep(wait_time)
                continue
            else:
                st.error(f"❌ Error al abrir la hoja de cálculo después de {max_retries} intentos: {str(e)}")
                st.stop()
        except gspread.SpreadsheetNotFound:
            st.error(f"❌ No se encontró el archivo '{SPREADSHEET_NAME}' en tu cuenta de Google.")
            st.stop()
        except Exception as e:
            st.error(f"❌ Error inesperado al abrir la hoja de cálculo: {str(e)}")
            st.stop()

sheet = get_sheet_with_retry()

# ============================================================
# DEFINICIÓN DE CAMPOS Y CONFIGURACIONES
# ============================================================
CAMPOS_POLIZA = [
    "No. Cliente", "CONTRATANTE", "ASEGURADO", "BENEFICIARIO",
    "FECHA DE NAC CONTRATANTE", "FECHA DE NAC ASEGURADO", "ESTADO CIVIL",
    "No. POLIZA", "INICIO DE VIGENCIA", "FIN DE VIGENCIA", "FORMA DE PAGO",
    "FRECUENCIA DE PAGO", "PRIMA ANUAL", "PRODUCTO", "No Serie Auto",
    "ASEGURADORA", "DIRECCIÓN", "TELEFONO", "EMAIL", "NOTAS", "DESCRIPCION AUTO"
]

ASEGURADORAS = [
    "ALLIANZ", "ANA SEGUROS", "BX+", "EL AGUILA", 
    "INSIGNIA LIFE", "MAPFRE", "QUALITAS"
]

OPCIONES_ESTADO_CIVIL = [
    "", "SOLTERO/A", "CASADO/A", "DIVORCIADO/A",
    "SEPARADO/A", "UNIÓN LIBRE", "VIUDO/A"
]

# ============================================================
# FUNCIONES PRINCIPALES
# ============================================================
def ensure_sheet_exists(sheet, title, headers):
    max_retries = 2
    for attempt in range(max_retries):
        try:
            worksheet = sheet.worksheet(title)
            return worksheet
        except gspread.WorksheetNotFound:
            try:
                worksheet = sheet.add_worksheet(title=title, rows="1000", cols=str(len(headers)))
                worksheet.append_row(headers)
                return worksheet
            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    return None
        except Exception as e:
            return None

@st.cache_data(ttl=300)
def obtener_polizas_cached():
    max_retries = 2
    for attempt in range(max_retries):
        try:
            return polizas_ws.get_all_records()
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                return []

def obtener_polizas():
    return obtener_polizas_cached()

@st.cache_data(ttl=300)
def obtener_cancelaciones_cached():
    max_retries = 2
    for attempt in range(max_retries):
        try:
            return cancelaciones_ws.get_all_records()
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                return []

def obtener_cancelaciones():
    return obtener_cancelaciones_cached()

def clear_polizas_cache():
    st.cache_data.clear()

def obtener_ultimo_id_cliente():
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
    except Exception:
        return 0

def generar_nuevo_id_cliente():
    ultimo_id = obtener_ultimo_id_cliente()
    return ultimo_id + 1

@st.cache_data(ttl=300)
def obtener_clientes_unicos_cached():
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
        
        return sorted(clientes.keys())
    except Exception:
        return []

def obtener_clientes_unicos():
    return obtener_clientes_unicos_cached()

def buscar_por_nombre_cliente(nombre_cliente):
    try:
        polizas = obtener_polizas()
        resultados = [p for p in polizas if p.get("CONTRATANTE", "") == nombre_cliente]
        return resultados
    except Exception:
        return []

def agregar_poliza(datos):
    max_retries = 2
    for attempt in range(max_retries):
        try:
            datos_str = [str(dato) if dato is not None else "" for dato in datos]
            polizas_ws.append_row(datos_str)
            clear_polizas_cache()
            return True
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                return False

def mover_a_cancelaciones(datos):
    max_retries = 2
    for attempt in range(max_retries):
        try:
            datos_str = [str(dato) if dato is not None else "" for dato in datos]
            cancelaciones_ws.append_row(datos_str)
            clear_polizas_cache()
            return True
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                return False

@st.cache_data(ttl=600)
def obtener_polizas_proximas_vencer(dias=30):
    try:
        polizas = obtener_polizas()
        hoy = datetime.now().date()
        fecha_limite = hoy + timedelta(days=dias)
        
        polizas_proximas = []
        
        for poliza in polizas:
            fecha_fin = poliza.get("FIN DE VIGENCIA", "")
            if fecha_fin:
                try:
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
        return []

def obtener_cumpleaños_mes_actual():
    try:
        polizas = obtener_polizas()
        mes_actual = datetime.now().month
        
        cumpleaños_mes = []
        
        for poliza in polizas:
            fecha_nac = poliza.get("FECHA DE NAC CONTRATANTE", "")
            contratante = poliza.get("CONTRATANTE", "")
            
            if fecha_nac and contratante:
                try:
                    for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y']:
                        try:
                            fecha_nac_dt = datetime.strptime(fecha_nac, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        continue
                    
                    if fecha_nac_dt.month == mes_actual:
                        cumpleaños_mes.append({
                            "CONTRATANTE": contratante,
                            "FECHA DE NACIMIENTO": fecha_nac_dt.strftime('%d/%m/%Y'),
                            "DÍA": fecha_nac_dt.day
                        })
                        
                except Exception:
                    continue
        
        cumpleaños_mes.sort(key=lambda x: x["DÍA"])
        return cumpleaños_mes
        
    except Exception as e:
        return []

# ============================================================
# INICIALIZAR HOJAS DE TRABAJO
# ============================================================
polizas_ws = ensure_sheet_exists(sheet, "Polizas", CAMPOS_POLIZA)
if polizas_ws is None:
    st.error("❌ No se pudo inicializar la hoja de pólizas")
    st.stop()

cancelaciones_ws = ensure_sheet_exists(sheet, "Cancelaciones", CAMPOS_POLIZA)
if cancelaciones_ws is None:
    st.error("❌ No se pudo inicializar la hoja de cancelaciones")
    st.stop()

# ============================================================
# INTERFAZ PRINCIPAL
# ============================================================
st.title("🏢 Sistema de Gestión de Pólizas")
st.markdown("---")

menu = st.sidebar.radio("Navegación", [
    "📝 Data Entry - Nueva Póliza", 
    "🔍 Consultar Pólizas por Cliente", 
    "⏳ Pólizas Próximas a Vencer",
    "📊 Ver Todas las Pólizas",
    "🎂 Cumpleaños del Mes",
    "🗑️ Ver Cancelaciones"
])

if st.sidebar.button("🔄 Limpiar Cache"):
    clear_polizas_cache()
    st.rerun()
import uuid  # Agregar esta importación al inicio del archivo

# ============================================================
# DATA ENTRY - NUEVA PÓLIZA (SOLUCIÓN CON UUID)
# ============================================================
if menu == "📝 Data Entry - Nueva Póliza":
    st.header("📝 Ingresar Nueva Póliza")
    
    # Calcular ID pero no mostrarlo
    nuevo_id = generar_nuevo_id_cliente()
    
    # Inicializar estado y clave del formulario
    if 'datos_formulario' not in st.session_state:
        st.session_state.datos_formulario = {}
    if 'form_key' not in st.session_state:
        st.session_state.form_key = str(uuid.uuid4())
    
    # Función callback para limpiar el formulario
    def limpiar_formulario():
        st.session_state.datos_formulario = {}
        st.session_state.form_key = str(uuid.uuid4())  # Nueva clave para forzar reset
    
    # Botón para limpiar formulario (fuera del formulario)
    if st.button("🧹 Limpiar Formulario", use_container_width=True, type="secondary", 
                 on_click=limpiar_formulario):
        st.success("Formulario limpiado")
        st.rerun()
    
    # Usar formulario con clave única que cambia cuando queremos limpiar
    with st.form(f"form_nueva_poliza_{st.session_state.form_key}", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            contratante = st.text_input(
                "CONTRATANTE *", 
                value=st.session_state.datos_formulario.get("contratante", ""),
                key=f"contratante_{st.session_state.form_key}"
            )
            
            asegurado = st.text_input(
                "ASEGURADO *", 
                value=st.session_state.datos_formulario.get("asegurado", ""),
                key=f"asegurado_{st.session_state.form_key}"
            )
            
            beneficiario = st.text_input(
                "BENEFICIARIO", 
                value=st.session_state.datos_formulario.get("beneficiario", ""),
                key=f"beneficiario_{st.session_state.form_key}"
            )
            
            fecha_nac_contratante = st.text_input(
                "FECHA DE NAC CONTRATANTE (DD/MM/AAAA)", 
                placeholder="DD/MM/AAAA",
                value=st.session_state.datos_formulario.get("fecha_nac_contratante", ""),
                key=f"fecha_nac_contratante_{st.session_state.form_key}"
            )
            
            fecha_nac_asegurado = st.text_input(
                "FECHA DE NAC ASEGURADO (DD/MM/AAAA)", 
                placeholder="DD/MM/AAAA", 
                value=st.session_state.datos_formulario.get("fecha_nac_asegurado", ""),
                key=f"fecha_nac_asegurado_{st.session_state.form_key}"
            )
            
            estado_civil_val = st.session_state.datos_formulario.get("estado_civil", "")
            estado_civil_index = OPCIONES_ESTADO_CIVIL.index(estado_civil_val) if estado_civil_val in OPCIONES_ESTADO_CIVIL else 0
            estado_civil = st.selectbox(
                "ESTADO CIVIL", 
                options=OPCIONES_ESTADO_CIVIL,
                index=estado_civil_index,
                key=f"estado_civil_{st.session_state.form_key}"
            )
        
        with col2:
            no_poliza = st.text_input(
                "No. POLIZA *", 
                value=st.session_state.datos_formulario.get("no_poliza", ""),
                key=f"no_poliza_{st.session_state.form_key}"
            )
            
            inicio_vigencia = st.text_input(
                "INICIO DE VIGENCIA * (DD/MM/AAAA)", 
                placeholder="DD/MM/AAAA",
                value=st.session_state.datos_formulario.get("inicio_vigencia", ""),
                key=f"inicio_vigencia_{st.session_state.form_key}"
            )
            
            fin_vigencia = st.text_input(
                "FIN DE VIGENCIA * (DD/MM/AAAA)", 
                placeholder="DD/MM/AAAA",
                value=st.session_state.datos_formulario.get("fin_vigencia", ""),
                key=f"fin_vigencia_{st.session_state.form_key}"
            )
            
            forma_pago = st.text_input(
                "FORMA DE PAGO", 
                placeholder="Ej: Efectivo, Tarjeta, Transferencia, Débito Automático",
                value=st.session_state.datos_formulario.get("forma_pago", ""),
                key=f"forma_pago_{st.session_state.form_key}"
            )
            
            frecuencia_pago = st.text_input(
                "FRECUENCIA DE PAGO", 
                placeholder="Ej: Anual, Semestral, Trimestral, Mensual",
                value=st.session_state.datos_formulario.get("frecuencia_pago", ""),
                key=f"frecuencia_pago_{st.session_state.form_key}"
            )
            
            prima_anual_default = st.session_state.datos_formulario.get("prima_anual", 0.0)
            prima_anual = st.number_input(
                "PRIMA ANUAL", 
                min_value=0.0, 
                format="%.2f",
                value=float(prima_anual_default) if prima_anual_default else 0.0,
                key=f"prima_anual_{st.session_state.form_key}"
            )
            
            producto = st.text_input(
                "PRODUCTO", 
                value=st.session_state.datos_formulario.get("producto", ""),
                key=f"producto_{st.session_state.form_key}"
            )
        
        st.subheader("Información Adicional")
        col3, col4 = st.columns(2)
        
        with col3:
            no_serie_auto = st.text_input(
                "No Serie Auto", 
                value=st.session_state.datos_formulario.get("no_serie_auto", ""),
                key=f"no_serie_auto_{st.session_state.form_key}"
            )
            
            aseguradora_val = st.session_state.datos_formulario.get("aseguradora", "")
            aseguradora_index = ASEGURADORAS.index(aseguradora_val) if aseguradora_val in ASEGURADORAS else 0
            aseguradora = st.selectbox(
                "ASEGURADORA",
                options=ASEGURADORAS,
                index=aseguradora_index,
                key=f"aseguradora_{st.session_state.form_key}"
            )
            
            direccion = st.text_area(
                "DIRECCIÓN", 
                value=st.session_state.datos_formulario.get("direccion", ""),
                key=f"direccion_{st.session_state.form_key}"
            )
        
        with col4:
            telefono = st.text_input(
                "TELEFONO", 
                value=st.session_state.datos_formulario.get("telefono", ""),
                key=f"telefono_{st.session_state.form_key}"
            )
            
            email = st.text_input(
                "EMAIL", 
                value=st.session_state.datos_formulario.get("email", ""),
                key=f"email_{st.session_state.form_key}"
            )
            
            notas = st.text_area(
                "NOTAS", 
                value=st.session_state.datos_formulario.get("notas", ""),
                key=f"notas_{st.session_state.form_key}"
            )
            
            descripcion_auto = st.text_area(
                "DESCRIPCION AUTO", 
                value=st.session_state.datos_formulario.get("descripcion_auto", ""),
                key=f"descripcion_auto_{st.session_state.form_key}"
            )
        
        # Botones en la misma línea
        col_btn_submit, col_btn_clear = st.columns([3, 1])
        with col_btn_submit:
            submit_button = st.form_submit_button("💾 Guardar Póliza", use_container_width=True, type="primary")
        with col_btn_clear:
            # Botón de limpieza dentro del formulario
            clear_button = st.form_submit_button("🧹 Limpiar", use_container_width=True, type="secondary")

        # Procesar botón de limpieza dentro del formulario
        if clear_button:
            limpiar_formulario()
            st.success("Formulario limpiado")
            st.rerun()

        # Procesar envío del formulario
        if submit_button:
            # Guardar todos los datos en session_state antes de validar
            st.session_state.datos_formulario = {
                "contratante": contratante,
                "asegurado": asegurado,
                "beneficiario": beneficiario,
                "fecha_nac_contratante": fecha_nac_contratante,
                "fecha_nac_asegurado": fecha_nac_asegurado,
                "estado_civil": estado_civil,
                "no_poliza": no_poliza,
                "inicio_vigencia": inicio_vigencia,
                "fin_vigencia": fin_vigencia,
                "forma_pago": forma_pago,
                "frecuencia_pago": frecuencia_pago,
                "prima_anual": prima_anual,
                "producto": producto,
                "no_serie_auto": no_serie_auto,
                "aseguradora": aseguradora,
                "direccion": direccion,
                "telefono": telefono,
                "email": email,
                "notas": notas,
                "descripcion_auto": descripcion_auto
            }

            # Validar campos obligatorios
            campos_faltantes = []
            if not contratante:
                campos_faltantes.append("CONTRATANTE")
            if not asegurado:
                campos_faltantes.append("ASEGURADO")
            if not no_poliza:
                campos_faltantes.append("No. POLIZA")
            if not inicio_vigencia:
                campos_faltantes.append("INICIO DE VIGENCIA")
            if not fin_vigencia:
                campos_faltantes.append("FIN DE VIGENCIA")

            # Validar formatos de fecha
            errores_fecha = []
            
            if fecha_nac_contratante:
                valido, error = validar_fecha(fecha_nac_contratante, es_vigencia=False)
                if not valido:
                    errores_fecha.append(f"Fecha Nacimiento Contratante: {error}")
            
            if fecha_nac_asegurado:
                valido, error = validar_fecha(fecha_nac_asegurado, es_vigencia=False)
                if not valido:
                    errores_fecha.append(f"Fecha Nacimiento Asegurado: {error}")
            
            if inicio_vigencia:
                valido, error = validar_fecha(inicio_vigencia, es_vigencia=True)
                if not valido:
                    errores_fecha.append(f"Inicio Vigencia: {error}")
            
            if fin_vigencia:
                valido, error = validar_fecha(fin_vigencia, es_vigencia=True)
                if not valido:
                    errores_fecha.append(f"Fin Vigencia: {error}")

            # Mostrar errores
            if campos_faltantes:
                st.error(f"❌ Campos obligatorios faltantes: {', '.join(campos_faltantes)}")
            
            if errores_fecha:
                for error in errores_fecha:
                    st.error(error)

            # Solo guardar si no hay errores
            if not campos_faltantes and not errores_fecha:
                def obtener_id_cliente_o_nuevo(nombre_contratante):
                    polizas = obtener_polizas()
                    for p in polizas:
                        if p.get("CONTRATANTE", "").strip().lower() == nombre_contratante.strip().lower():
                            return p.get("No. Cliente", "")
                    return str(generar_nuevo_id_cliente())

                id_cliente = obtener_id_cliente_o_nuevo(contratante)

                datos_poliza = [
                    id_cliente,
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
                    str(prima_anual),
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
                    st.success("✅ ¡Póliza guardada exitosamente!")
                    st.balloons()
                    
                    # Limpiar formulario después de guardado exitoso
                    limpiar_formulario()
                    st.rerun()
                else:
                    st.error("❌ Error al guardar la póliza. Por favor intenta nuevamente.")
# ============================================================
# CONSULTAR PÓLIZAS POR CLIENTE
# ============================================================
elif menu == "🔍 Consultar Pólizas por Cliente":
    st.header("🔍 Consultar Pólizas por Cliente")
    
    clientes = obtener_clientes_unicos()
    
    if not clientes:
        st.info("ℹ️ No hay clientes registrados en el sistema")
    else:
        cliente_seleccionado = st.selectbox("Selecciona un cliente:", options=clientes, key="select_cliente")
        
        buscar_btn = st.button("🔍 Buscar Pólizas", key="buscar_polizas_btn", use_container_width=True)
        
        if buscar_btn and cliente_seleccionado:
            resultados = buscar_por_nombre_cliente(cliente_seleccionado)
            
            if resultados:
                df_resultados = pd.DataFrame(resultados)
                columnas_importantes = ["No. Cliente", "No. POLIZA", "PRODUCTO", "INICIO DE VIGENCIA", "FIN DE VIGENCIA", "PRIMA ANUAL", "ASEGURADORA"]
                columnas_disponibles = [col for col in columnas_importantes if col in df_resultados.columns]
                st.dataframe(df_resultados[columnas_disponibles], use_container_width=True)

# ============================================================
# PÓLIZAS PRÓXIMAS A VENCER
# ============================================================
elif menu == "⏳ Pólizas Próximas a Vencer":
    st.header("⏳ Pólizas Próximas a Vencer (Próximos 30 días)")
    
    polizas_proximas = obtener_polizas_proximas_vencer(30)
    
    if polizas_proximas:
        df_proximas = pd.DataFrame(polizas_proximas)
        columnas_vencimiento = ["No. Cliente", "CONTRATANTE", "No. POLIZA", "PRODUCTO", "FIN DE VIGENCIA", "PRIMA ANUAL", "TELEFONO", "EMAIL"]
        columnas_disponibles = [col for col in columnas_vencimiento if col in df_proximas.columns]
        st.dataframe(df_proximas[columnas_disponibles], use_container_width=True)
    else:
        st.info("ℹ️ No hay pólizas que venzan en los próximos 30 días")

# ============================================================
# VER TODAS LAS PÓLIZAS
# ============================================================
elif menu == "📊 Ver Todas las Pólizas":
    st.header("📊 Todas las Pólizas Registradas")
    
    todas_polizas = obtener_polizas()
    
    if todas_polizas:
        df_todas = pd.DataFrame(todas_polizas)
        st.dataframe(df_todas, use_container_width=True)
    else:
        st.info("ℹ️ No hay pólizas registradas en el sistema")

# ============================================================
# CUMPLEAÑOS DEL MES
# ============================================================
elif menu == "🎂 Cumpleaños del Mes":
    st.header("🎂 Cumpleaños del Mes")
    
    mes_actual = datetime.now().strftime("%B")
    st.subheader(f"Cumpleaños en {mes_actual}")
    
    cumpleaños = obtener_cumpleaños_mes_actual()
    
    if cumpleaños:
        df_cumpleaños = pd.DataFrame(cumpleaños)
        st.dataframe(df_cumpleaños[["CONTRATANTE", "FECHA DE NACIMIENTO", "DÍA"]], 
                    use_container_width=True,
                    column_config={
                        "CONTRATANTE": "Contratante",
                        "FECHA DE NACIMIENTO": "Fecha de Nacimiento",
                        "DÍA": "Día del Mes"
                    })
    else:
        st.info("ℹ️ No hay contratantes que cumplan años este mes")

# ============================================================
# VER CANCELACIONES
# ============================================================
elif menu == "🗑️ Ver Cancelaciones":
    st.header("🗑️ Pólizas Canceladas")
    
    cancelaciones = obtener_cancelaciones()
    
    if cancelaciones:
        df_cancelaciones = pd.DataFrame(cancelaciones)
        columnas_importantes = ["No. Cliente", "CONTRATANTE", "No. POLIZA", "PRODUCTO", "INICIO DE VIGENCIA", "FIN DE VIGENCIA", "PRIMA ANUAL", "ASEGURADORA"]
        columnas_disponibles = [col for col in columnas_importantes if col in df_cancelaciones.columns]
        st.dataframe(df_cancelaciones[columnas_disponibles], use_container_width=True)
    else:
        st.info("ℹ️ No hay pólizas canceladas en el historial")
# ============================================================
# 2. CONSULTAR PÓLIZAS POR CLIENTE (CON DUPICACIÓN Y ELIMINACIÓN)
# ============================================================
elif menu == "🔍 Consultar Pólizas por Cliente":
    st.header("🔍 Consultar Pólizas por Cliente")
    
    # Lista de aseguradoras predefinidas (misma que en Data Entry)
    ASEGURADORAS = [
        "ALLIANZ",
        "ANA SEGUROS", 
        "BX+",
        "EL AGUILA",
        "INSIGNIA LIFE",
        "MAPFRE",
        "QUALITAS"
    ]
    
    # Opciones actualizadas para estado civil (misma que en Data Entry)
    OPCIONES_ESTADO_CIVIL = [
        "",
        "SOLTERO/A",
        "CASADO/A", 
        "DIVORCIADO/A",
        "SEPARADO/A",
        "UNIÓN LIBRE",
        "VIUDO/A"
    ]
    
    # Inicializar estados de sesión
    if 'cliente_buscado' not in st.session_state:
        st.session_state.cliente_buscado = None
    if 'resultados_busqueda' not in st.session_state:
        st.session_state.resultados_busqueda = []
    if 'mostrar_duplicacion' not in st.session_state:
        st.session_state.mostrar_duplicacion = False
    if 'poliza_a_duplicar' not in st.session_state:
        st.session_state.poliza_a_duplicar = None
    if 'mostrar_eliminacion' not in st.session_state:
        st.session_state.mostrar_eliminacion = False
    if 'poliza_a_eliminar' not in st.session_state:
        st.session_state.poliza_a_eliminar = None
    
    # Obtener lista de clientes únicos para el dropdown
    try:
        clientes = obtener_clientes_unicos()
    except Exception as e:
        st.error(f"❌ Error al cargar lista de clientes: {str(e)}")
        st.info("🔄 Intentando cargar datos desde cache...")
        clientes = []
    
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
            
            # Botones en columnas separadas para evitar conflicto
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                buscar_btn = st.button("🔍 Buscar Pólizas", key="buscar_polizas_btn", use_container_width=True)
            with col_btn2:
                if st.session_state.cliente_buscado:
                    limpiar_btn = st.button("🔄 Nueva Búsqueda", key="limpiar_busqueda_btn", use_container_width=True)
                    if limpiar_btn:
                        st.session_state.cliente_buscado = None
                        st.session_state.resultados_busqueda = []
                        st.session_state.mostrar_duplicacion = False
                        st.session_state.poliza_a_duplicar = None
                        st.session_state.mostrar_eliminacion = False
                        st.session_state.poliza_a_eliminar = None
                        st.rerun()
        
        # Manejar la búsqueda
        if buscar_btn and cliente_seleccionado:
            with st.spinner("Buscando pólizas..."):
                try:
                    resultados = buscar_por_nombre_cliente(cliente_seleccionado)
                    st.session_state.cliente_buscado = cliente_seleccionado
                    st.session_state.resultados_busqueda = resultados
                    st.session_state.mostrar_duplicacion = False
                    st.session_state.poliza_a_duplicar = None
                    st.session_state.mostrar_eliminacion = False
                    st.session_state.poliza_a_eliminar = None
                except Exception as e:
                    st.error(f"❌ Error al buscar pólizas: {str(e)}")
        
        # Mostrar resultados si hay una búsqueda activa
        if st.session_state.cliente_buscado and st.session_state.resultados_busqueda:
            resultados = st.session_state.resultados_busqueda
            cliente_seleccionado = st.session_state.cliente_buscado
            
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
            # FUNCIONALIDAD: ELIMINAR PÓLIZA (AHORA MOVER A CANCELACIONES)
            # ============================================================
            st.markdown("---")
            st.subheader("🗑️ Cancelar Póliza")
            
            # Seleccionar póliza a eliminar
            polizas_para_eliminar = [f"{p['No. POLIZA']} - {p['PRODUCTO']} (Vence: {p.get('FIN DE VIGENCIA', 'N/A')})" 
                                   for p in resultados]
            
            if polizas_para_eliminar:
                # Usar un contenedor para agrupar la selección de póliza a eliminar
                with st.container():
                    poliza_eliminar_idx = st.selectbox(
                        "Selecciona la póliza a cancelar:",
                        options=range(len(polizas_para_eliminar)),
                        format_func=lambda x: polizas_para_eliminar[x],
                        key="select_poliza_eliminar_idx"
                    )
                    
                    seleccionar_eliminar_btn = st.button("📝 Seleccionar para Cancelar", key="seleccionar_eliminar_btn")
                    
                    if seleccionar_eliminar_btn and poliza_eliminar_idx is not None:
                        st.session_state.mostrar_eliminacion = True
                        st.session_state.poliza_a_eliminar = resultados[poliza_eliminar_idx]
                
                # Mostrar confirmación de eliminación si está activo
                if st.session_state.mostrar_eliminacion and st.session_state.poliza_a_eliminar:
                    poliza_eliminar = st.session_state.poliza_a_eliminar
                    
                    st.warning(f"⚠️ **ESTÁS A PUNTO DE CANCELAR LA SIGUIENTE PÓLIZA:**")
                    st.error(f"**No. Póliza:** {poliza_eliminar['No. POLIZA']}")
                    st.error(f"**Producto:** {poliza_eliminar['PRODUCTO']}")
                    st.error(f"**Cliente:** {poliza_eliminar['CONTRATANTE']}")
                    st.error(f"**Vigencia:** {poliza_eliminar.get('INICIO DE VIGENCIA', 'N/A')} - {poliza_eliminar.get('FIN DE VIGENCIA', 'N/A')}")
                    
                    # Mostrar más detalles de la póliza a eliminar
                    with st.expander("📋 Ver todos los detalles de la póliza a cancelar"):
                        st.write(poliza_eliminar)
                    
                    col_elim1, col_elim2, col_elim3 = st.columns([1, 2, 1])
                    with col_elim2:
                        confirmar_eliminar_btn = st.button("🗑️ CONFIRMAR CANCELACIÓN", 
                                                         type="primary", 
                                                         key="confirmar_eliminar_btn",
                                                         use_container_width=True)
                    
                    if confirmar_eliminar_btn:
                        # Función para eliminar póliza (ahora mover a cancelaciones)
                        def cancelar_poliza(poliza_data):
                            try:
                                # Preparar datos para mover a cancelaciones
                                datos_cancelacion = [
                                    poliza_data.get('No. Cliente', ''),
                                    poliza_data.get('CONTRATANTE', ''),
                                    poliza_data.get('ASEGURADO', ''),
                                    poliza_data.get('BENEFICIARIO', ''),
                                    poliza_data.get('FECHA DE NAC CONTRATANTE', ''),
                                    poliza_data.get('FECHA DE NAC ASEGURADO', ''),
                                    poliza_data.get('ESTADO CIVIL', ''),
                                    poliza_data.get('No. POLIZA', ''),
                                    poliza_data.get('INICIO DE VIGENCIA', ''),
                                    poliza_data.get('FIN DE VIGENCIA', ''),
                                    poliza_data.get('FORMA DE PAGO', ''),
                                    poliza_data.get('FRECUENCIA DE PAGO', ''),
                                    poliza_data.get('PRIMA ANUAL', ''),
                                    poliza_data.get('PRODUCTO', ''),
                                    poliza_data.get('No Serie Auto', ''),
                                    poliza_data.get('ASEGURADORA', ''),
                                    poliza_data.get('DIRECCIÓN', ''),
                                    poliza_data.get('TELEFONO', ''),
                                    poliza_data.get('EMAIL', ''),
                                    poliza_data.get('NOTAS', ''),
                                    poliza_data.get('DESCRIPCION AUTO', '')
                                ]
                                
                                # Mover a cancelaciones
                                if mover_a_cancelaciones(datos_cancelacion):
                                    # Ahora eliminar de pólizas activas
                                    todas_polizas = polizas_ws.get_all_records()
                                    for i, poliza in enumerate(todas_polizas, start=2):  # start=2 porque fila 1 son encabezados
                                        if poliza.get('No. POLIZA') == poliza_data['No. POLIZA']:
                                            polizas_ws.delete_rows(i)
                                            break
                                    
                                    return True
                                return False
                            except Exception as e:
                                st.error(f"❌ Error al cancelar póliza: {str(e)}")
                                return False
                        
                        if cancelar_poliza(poliza_eliminar):
                            st.success(f"✅ Póliza {poliza_eliminar['No. POLIZA']} cancelada exitosamente y movida al historial de cancelaciones!")
                            
                            # Resetear estado de eliminación y actualizar resultados
                            st.session_state.mostrar_eliminacion = False
                            st.session_state.poliza_a_eliminar = None
                            
                            # Actualizar la lista de resultados
                            with st.spinner("Actualizando lista de pólizas..."):
                                nuevos_resultados = buscar_por_nombre_cliente(cliente_seleccionado)
                                st.session_state.resultados_busqueda = nuevos_resultados
                            
                            st.rerun()
                        else:
                            st.error("❌ Error al cancelar la póliza. Por favor intenta nuevamente.")
            
            # ============================================================
            # FUNCIONALIDAD EXISTENTE: DUPLICAR PÓLIZA
            # ============================================================
            st.markdown("---")
            st.subheader("🔄 Duplicar Póliza")
            
            # Seleccionar póliza a duplicar
            polizas_para_duplicar = [f"{p['No. POLIZA']} - {p['PRODUCTO']} (Vence: {p.get('FIN DE VIGENCIA', 'N/A')})" 
                                   for p in resultados]
            
            if polizas_para_duplicar:
                # Usar un contenedor para agrupar la selección de póliza
                with st.container():
                    poliza_seleccionada_idx = st.selectbox(
                        "Selecciona la póliza a duplicar:",
                        options=range(len(polizas_para_duplicar)),
                        format_func=lambda x: polizas_para_duplicar[x],
                        key="select_poliza_duplicar_idx"
                    )
                    
                    seleccionar_btn = st.button("📝 Seleccionar para Duplicar", key="seleccionar_duplicar_btn")
                    
                    if seleccionar_btn and poliza_seleccionada_idx is not None:
                        st.session_state.mostrar_duplicacion = True
                        st.session_state.poliza_a_duplicar = resultados[poliza_seleccionada_idx]
                
                # Mostrar formulario de duplicación si está activo
                if st.session_state.mostrar_duplicacion and st.session_state.poliza_a_duplicar:
                    poliza_original = st.session_state.poliza_a_duplicar
                    
                    st.info(f"📋 Duplicando póliza: {poliza_original['No. POLIZA']} - {poliza_original['PRODUCTO']}")
                    
                    # Crear un formulario separado para la duplicación
                    with st.form(key="form_duplicar_poliza", clear_on_submit=True):
                        st.write("**Complete los nuevos datos para la póliza duplicada:**")
                        
                        col_dup1, col_dup2 = st.columns(2)
                        
                        with col_dup1:
                            nuevo_no_poliza = st.text_input(
                                "Nuevo No. POLIZA *",
                                value="",
                                key="nuevo_no_poliza_form"
                            )
                            nuevo_inicio_vigencia = st.text_input(
                                "Nuevo INICIO DE VIGENCIA * (DD/MM/AAAA)",
                                placeholder="DD/MM/AAAA",
                                key="nuevo_inicio_vigencia_form"
                            )
                            nuevo_fin_vigencia = st.text_input(
                                "Nuevo FIN DE VIGENCIA * (DD/MM/AAAA)",
                                placeholder="DD/MM/AAAA",
                                key="nuevo_fin_vigencia_form"
                            )
                            
                            # Campo para modificar forma de pago en duplicación
                            nueva_forma_pago = st.text_input(
                                "FORMA DE PAGO",
                                value=poliza_original.get('FORMA DE PAGO', ''),
                                placeholder="Ej: Efectivo, Tarjeta, Transferencia, Débito Automático",
                                key="nueva_forma_pago_form"
                            )
                            
                            nueva_prima_anual = st.number_input(
                                "Nueva PRIMA ANUAL",
                                value=float(poliza_original.get('PRIMA ANUAL', 0) or 0),
                                min_value=0.0,
                                format="%.2f",
                                key="nueva_prima_anual_form"
                            )
                        
                        with col_dup2:
                            nuevo_producto = st.text_input(
                                "PRODUCTO",
                                value=poliza_original.get('PRODUCTO', ''),
                                key="nuevo_producto_form"
                            )
                            
                            # Lista desplegable de aseguradoras predefinidas en duplicación
                            nueva_aseguradora = st.selectbox(
                                "ASEGURADORA",
                                options=ASEGURADORAS,
                                key="nueva_aseguradora_form"
                            )
                            
                            # Campo para modificar frecuencia de pago en duplicación
                            nueva_frecuencia_pago = st.text_input(
                                "FRECUENCIA DE PAGO",
                                value=poliza_original.get('FRECUENCIA DE PAGO', ''),
                                placeholder="Ej: Anual, Semestral, Trimestral, Mensual",
                                key="nueva_frecuencia_pago_form"
                            )
                            
                            # Campo para modificar estado civil en duplicación
                            nuevo_estado_civil = st.selectbox(
                                "ESTADO CIVIL",
                                options=OPCIONES_ESTADO_CIVIL,
                                key="nuevo_estado_civil_form"
                            )
                            
                            nuevas_notas = st.text_area(
                                "NOTAS",
                                value=poliza_original.get('NOTAS', ''),
                                key="nuevas_notas_form"
                            )
                        
                        # Botón para duplicar dentro del formulario
                        col_btn_dup1, col_btn_dup2, col_btn_dup3 = st.columns([1, 2, 1])
                        with col_btn_dup2:
                            duplicar_btn = st.form_submit_button("✅ Duplicar Póliza", use_container_width=True)
                        
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
                                    nuevo_estado_civil,  # Estado civil modificable
                                    nuevo_no_poliza,  # Nuevo número de póliza
                                    nuevo_inicio_vigencia,  # Nueva fecha de inicio
                                    nuevo_fin_vigencia,  # Nueva fecha de fin
                                    nueva_forma_pago,  # Forma de pago modificable
                                    nueva_frecuencia_pago,  # Frecuencia de pago modificable
                                    str(nueva_prima_anual),  # Prima puede ser modificada
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
                                    # Resetear estado de duplicación
                                    st.session_state.mostrar_duplicacion = False
                                    st.session_state.poliza_a_duplicar = None
                                    st.rerun()
                                else:
                                    st.error("❌ Error al guardar la póliza duplicada. Por favor intenta nuevamente.")
                
                # Descargar resultados
                st.markdown("---")
                csv = df_resultados.to_csv(index=False, encoding='utf-8')
                st.download_button(
                    label="📥 Descargar resultados en CSV",
                    data=csv,
                    file_name=f"polizas_cliente_{cliente_seleccionado.replace(' ', '_')}.csv",
                    mime="text/csv",
                    key="descargar_csv_btn"
                )

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
                # Manejo robusto de la suma de primas
                try:
                    primas_numericas = pd.to_numeric(df_proximas['PRIMA ANUAL'], errors='coerce').fillna(0)
                    prima_total = primas_numericas.sum()
                    st.metric("Prima Total", f"${prima_total:,.2f}")
                except Exception as e:
                    st.metric("Prima Total", "Error")
                    st.error(f"❌ Error al calcular prima total: {str(e)}")
        
        # Descargar reporte
        csv = df_proximas.to_csv(index=False, encoding='utf-8')
        st.download_button(
            label="📥 Descargar Reporte de Vencimientos",
            data=csv,
            file_name=f"polizas_proximas_vencer_{datetime.now().strftime('%Y-%m-%d')}.csv",
            mime="text/csv",
            key="descargar_vencimientos_btn"
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
            # Manejo seguro de valores únicos para producto
            if 'PRODUCTO' in df_todas.columns:
                # Convertir a string y eliminar valores NaN antes de ordenar
                productos_unicos = df_todas['PRODUCTO'].dropna().astype(str).unique()
                opciones_producto = [""] + sorted(productos_unicos)
            else:
                opciones_producto = [""]

            filtro_producto = st.selectbox("Filtrar por Producto", opciones_producto)
            
        with col2:
            # Manejo seguro de valores únicos para aseguradora
            if 'ASEGURADORA' in df_todas.columns:
                # Convertir a string y eliminar valores NaN antes de ordenar
                aseguradoras_unicas = df_todas['ASEGURADORA'].dropna().astype(str).unique()
                opciones_aseguradora = [""] + sorted(aseguradoras_unicas)
            else:
                opciones_aseguradora = [""]

            filtro_aseguradora = st.selectbox("Filtrar por Aseguradora", opciones_aseguradora)
        
        # Aplicar filtros
        if filtro_producto:
            df_todas = df_todas[df_todas['PRODUCTO'].astype(str) == filtro_producto]
        if filtro_aseguradora:
            df_todas = df_todas[df_todas['ASEGURADORA'].astype(str) == filtro_aseguradora]
        
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
                # Manejo robusto de la suma de primas
                try:
                    primas_numericas = pd.to_numeric(df_todas['PRIMA ANUAL'], errors='coerce').fillna(0)
                    prima_total = primas_numericas.sum()
                    st.metric("Prima Anual Total", f"${prima_total:,.2f}")
                except Exception as e:
                    st.metric("Prima Anual Total", "Error")
                    st.error(f"❌ Error al calcular prima total: {str(e)}")
        with col4:
            if 'PRODUCTO' in df_todas.columns:
                st.metric("Productos Diferentes", df_todas['PRODUCTO'].nunique())
        
        # Descargar datos completos
        csv = df_todas.to_csv(index=False, encoding='utf-8')
        st.download_button(
            label="📥 Descargar Base Completa en CSV",
            data=csv,
            file_name=f"base_polizas_completa_{datetime.now().strftime('%Y-%m-%d')}.csv",
            mime="text/csv",
            key="descargar_completa_btn"
        )
    else:
        st.info("ℹ️ No hay pólizas registradas en el sistema")

# ============================================================
# 5. NUEVA SECCIÓN: CUMPLEAÑOS DEL MES
# ============================================================
elif menu == "🎂 Cumpleaños del Mes":
    st.header("🎂 Cumpleaños del Mes")
    
    mes_actual = datetime.now().strftime("%B")  # Nombre del mes actual
    st.subheader(f"Cumpleaños en {mes_actual}")
    
    with st.spinner("Buscando cumpleaños del mes..."):
        cumpleaños = obtener_cumpleaños_mes_actual()
    
    if cumpleaños:
        st.success(f"🎉 Se encontraron {len(cumpleaños)} contratantes que cumplen años este mes")
        
        # Crear DataFrame para mostrar
        df_cumpleaños = pd.DataFrame(cumpleaños)
        
        # Mostrar en una tabla ordenada por día
        st.dataframe(df_cumpleaños[["CONTRATANTE", "FECHA DE NACIMIENTO", "DÍA"]], 
                    use_container_width=True,
                    column_config={
                        "CONTRATANTE": "Contratante",
                        "FECHA DE NACIMIENTO": "Fecha de Nacimiento",
                        "DÍA": "Día del Mes"
                    })
        
        # Estadísticas rápidas
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Cumpleaños", len(cumpleaños))
        with col2:
            if cumpleaños:
                hoy = datetime.now().day
                # Contar cuántos cumplen hoy
                cumple_hoy = sum(1 for c in cumpleaños if c["DÍA"] == hoy)
                st.metric("Cumpleaños Hoy", cumple_hoy)
        
        # Descargar lista de cumpleaños
        csv = df_cumpleaños.to_csv(index=False, encoding='utf-8')
        st.download_button(
            label="📥 Descargar Lista de Cumpleaños",
            data=csv,
            file_name=f"cumpleaños_{datetime.now().strftime('%Y_%m')}.csv",
            mime="text/csv",
            key="descargar_cumpleaños_btn"
        )
    else:
        st.info("ℹ️ No hay contratantes que cumplan años este mes")

# ============================================================
# 6. NUEVA SECCIÓN: VER CANCELACIONES
# ============================================================
elif menu == "🗑️ Ver Cancelaciones":
    st.header("🗑️ Pólizas Canceladas")
    
    with st.spinner("Cargando cancelaciones..."):
        cancelaciones = obtener_cancelaciones()
    
    if cancelaciones:
        st.info(f"📋 Se encontraron {len(cancelaciones)} póliza(s) canceladas")
        
        df_cancelaciones = pd.DataFrame(cancelaciones)
        
        # Columnas importantes para mostrar
        columnas_importantes = ["No. Cliente", "CONTRATANTE", "No. POLIZA", "PRODUCTO", "INICIO DE VIGENCIA", "FIN DE VIGENCIA", "PRIMA ANUAL", "ASEGURADORA"]
        columnas_disponibles = [col for col in columnas_importantes if col in df_cancelaciones.columns]
        
        st.dataframe(df_cancelaciones[columnas_disponibles], use_container_width=True)
        
        # Opción para ver todos los detalles
        with st.expander("📋 Ver detalles completos de todas las cancelaciones"):
            st.dataframe(df_cancelaciones, use_container_width=True)
        
        # Estadísticas
        st.subheader("📈 Estadísticas de Cancelaciones")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Cancelaciones", len(df_cancelaciones))
        with col2:
            st.metric("Clientes Únicos", df_cancelaciones['No. Cliente'].nunique() if 'No. Cliente' in df_cancelaciones.columns else 0)
        with col3:
            if 'PRIMA ANUAL' in df_cancelaciones.columns:
                # Manejo robusto de la suma de primas
                try:
                    primas_numericas = pd.to_numeric(df_cancelaciones['PRIMA ANUAL'], errors='coerce').fillna(0)
                    prima_total = primas_numericas.sum()
                    st.metric("Prima Total Cancelada", f"${prima_total:,.2f}")
                except Exception as e:
                    st.metric("Prima Total Cancelada", "Error")
        
        # Descargar cancelaciones
        csv = df_cancelaciones.to_csv(index=False, encoding='utf-8')
        st.download_button(
            label="📥 Descargar Historial de Cancelaciones",
            data=csv,
            file_name=f"cancelaciones_{datetime.now().strftime('%Y-%m-%d')}.csv",
            mime="text/csv",
            key="descargar_cancelaciones_btn"
        )
    else:
        st.info("ℹ️ No hay pólizas canceladas en el historial")

# ============================================================
# INFORMACIÓN ADICIONAL EN SIDEBAR
# ============================================================
st.sidebar.markdown("---")
st.sidebar.info("""
**💡 Instrucciones:**
- **Data Entry**: Completa los campos y haz clic en Guardar
- **Consultar**: Busca por nombre del cliente y duplica/cancela pólizas  
- **Vencimientos**: Revisa pólizas que vencerán pronto
- **Ver Todo**: Explora toda la base de datos
- **Cumpleaños**: Ve quién cumple años este mes
- **Cancelaciones**: Historial de pólizas canceladas

**🔄 Si ves errores de cuota:**
- Usa el botón "Limpiar Cache"
- Espera unos minutos antes de continuar
- Los datos se cachean para reducir llamadas a la API
""")

# Mostrar estadísticas rápidas en sidebar
try:
    todas_polizas = obtener_polizas()
    if todas_polizas:
        df_temp = pd.DataFrame(todas_polizas)
        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 Resumen")
        st.sidebar.write(f"**Pólizas activas:** {len(df_temp)}")
        st.sidebar.write(f"**Clientes únicos:** {df_temp['No. Cliente'].nunique() if 'No. Cliente' in df_temp.columns else 'N/A'}")
        
        # Pólizas próximas a vencer
        proximas = obtener_polizas_proximas_vencer(30)
        st.sidebar.write(f"**Próximas a vencer (30 días):** {len(proximas)}")
        
        # Cumpleaños del mes
        cumpleaños = obtener_cumpleaños_mes_actual()
        st.sidebar.write(f"**Cumpleaños este mes:** {len(cumpleaños)}")
        
        # Cancelaciones
        cancelaciones = obtener_cancelaciones()
        st.sidebar.write(f"**Pólizas canceladas:** {len(cancelaciones)}")
        
        # Mostrar último ID utilizado
        ultimo_id = obtener_ultimo_id_cliente()
        st.sidebar.write(f"**Último ID utilizado:** {ultimo_id}")
except:
    pass






