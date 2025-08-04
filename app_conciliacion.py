import streamlit as st
import pandas as pd
from datetime import datetime
import chardet

st.set_page_config(page_title="Conciliación Diario Fudo & Klap", layout="centered")

# === LOGO ===
st.markdown(
    """
    <div style="text-align: center;">
        <img src="https://raw.githubusercontent.com/BadJoe-analyst/willow/main/logo.jpeg" width="200"/>
        <h2 style="margin-top: 0;">Willow Café</h2>
    </div>
    """,
    unsafe_allow_html=True
)

st.title("📊 Conciliación de Ventas: Fudo vs Klap")

st.markdown("""
### 📌 Instrucciones:
1. Sube los archivos exportados de Fudo y Klap en formato CSV.
2. El archivo de Fudo debe omitir manualmente las primeras 3 filas antes de exportar.
3. Esta app detecta automáticamente la fecha contenida en el archivo de Fudo.
""")

# === CARGA DE ARCHIVOS SEPARADOS ===
st.subheader("⬆️ Subida de archivos")
fudo_file = st.file_uploader("Archivo Fudo (.csv)", type=["csv"], key="fudo")
klap_file = st.file_uploader("Archivo Klap (.csv)", type=["csv"], key="klap")

def detectar_encoding(file):
    rawdata = file.read()
    file.seek(0)
    resultado = chardet.detect(rawdata)
    return resultado['encoding']

if fudo_file and klap_file:
    try:
        enc_fudo = detectar_encoding(fudo_file)
        enc_klap = detectar_encoding(klap_file)

        # Intentar cargar Fudo con separador ; primero
        try:
            df_fudo = pd.read_csv(fudo_file, sep=';', encoding=enc_fudo, skiprows=3, on_bad_lines='skip')
            if len(df_fudo.columns) == 1:
                raise ValueError("Separador incorrecto detectado")
        except:
            fudo_file.seek(0)
            df_fudo = pd.read_csv(fudo_file, sep=',', encoding=enc_fudo, skiprows=3, on_bad_lines='skip')

        # Klap fijo con ;
        df_klap = pd.read_csv(klap_file, sep=';', encoding=enc_klap, on_bad_lines='skip')

        # Parseo de fechas y montos
        df_fudo["Fecha"] = pd.to_datetime(df_fudo["Fecha"], dayfirst=True, errors='coerce')
        df_fudo["Total"] = pd.to_numeric(df_fudo["Total"], errors='coerce').fillna(0)
        df_klap["Fecha"] = pd.to_datetime(df_klap["Fecha"], dayfirst=True, errors='coerce')
        df_klap["Monto"] = pd.to_numeric(df_klap["Monto"], errors='coerce').fillna(0)

        if df_fudo["Fecha"].dropna().empty:
            st.error("❌ No se pudo detectar ninguna fecha válida en el archivo Fudo.")
            st.stop()

        # Detectar fecha automáticamente desde Fudo
        fecha_detectada = df_fudo["Fecha"].dropna().dt.date.mode()[0]
        st.success(f"📅 Fecha detectada: {fecha_detectada.strftime('%d-%m-%Y')}")

        # Mostrar fechas detectadas reales para debug
        fechas_fudo = df_fudo["Fecha"].dt.date.dropna().unique()
        fechas_klap = df_klap["Fecha"].dt.date.dropna().unique()

        # Filtrar por fecha
        fudo_dia = df_fudo[df_fudo["Fecha"].dt.date == fecha_detectada].copy()
        klap_dia = df_klap[df_klap["Fecha"].dt.date == fecha_detectada].copy()

        # Filtrar estado cerrado en Fudo
        fudo_dia = fudo_dia[fudo_dia["Estado"].str.strip() == "Cerrada"]

        # Filtrar estado aprobado en Klap
        df_klap["Estado"] = df_klap["Estado"].astype(str)
        df_klap["Estado"] = df_klap["Estado"].str.strip().str.lower()
        df_klap_aprobado = df_klap[df_klap["Estado"] == "aprobado"]
        klap_dia = df_klap_aprobado[df_klap_aprobado["Fecha"].dt.date == fecha_detectada].copy()

        if fudo_dia.empty:
            st.warning(f"⚠️ No se encontraron registros cerrados en Fudo para la fecha detectada.\nFechas con ventas en Fudo: {fechas_fudo}")
        if klap_dia.empty:
            st.warning(f"⚠️ No se encontraron transacciones aprobadas en Klap para la fecha detectada.\nFechas con transacciones en Klap: {fechas_klap}")
        
        if fudo_dia.empty or klap_dia.empty:
            st.stop()

        # Normalizar métodos de pago
        fudo_dia["Medio de Pago Normalizado"] = fudo_dia["Medio de Pago"].replace({
            "Tarj. Dbito": "Tarjeta",
            "Tarj. Débito": "Tarjeta",
            "Tarj. Crédito": "Tarjeta",
            "Tarj. Crdito": "Tarjeta",
            "Tarj Débito": "Tarjeta",
            "Tarjeta Débito": "Tarjeta",
            "Cta. Cte.": "Cuentas Abiertas"
        }).fillna("No Asignado")

        # Agrupar
        fudo_agg = fudo_dia.groupby("Medio de Pago Normalizado")["Total"].sum().reset_index()
        fudo_pivot = fudo_agg.pivot_table(index=None, columns="Medio de Pago Normalizado", values="Total", aggfunc="sum").fillna(0)

        for col in ["Efectivo", "Tarjeta", "Transferencia", "Cuentas Abiertas"]:
            if col not in fudo_pivot.columns:
                fudo_pivot[col] = 0

        # Totales
        efectivo = fudo_pivot["Efectivo"].values[0]
        tarjeta = fudo_pivot["Tarjeta"].values[0]
        transferencia = fudo_pivot["Transferencia"].values[0]
        cuentas_abiertas = fudo_pivot["Cuentas Abiertas"].values[0]
        total_fudo = fudo_dia["Total"].sum()
        total_klap = klap_dia["Monto"].sum()
        suma_medios = efectivo + tarjeta + transferencia + cuentas_abiertas

        # Mostrar tabla
        st.subheader("🔎 Resumen Conciliación")
        resumen_df = pd.DataFrame.from_dict({
            "Cash": [efectivo],
            "Card": [tarjeta],
            "Voucher": [transferencia],
            "Fudo Pagos": [cuentas_abiertas],
            "Total Fudo": [total_fudo],
            "TX Klap": [total_klap]
        })
        st.dataframe(resumen_df.style.format("$ {:,.0f}"))

        # Alertas con diferencia numérica clara
        if abs(total_fudo - suma_medios) > 0:
            diff = total_fudo - suma_medios
            st.error(f"⚠️ Total Fudo: ${total_fudo:,.0f} vs. Suma de medios: ${suma_medios:,.0f} → Diferencia: ${diff:,.0f}")

        if abs(tarjeta - total_klap) > 0:
            diff_card = tarjeta - total_klap
            st.warning(f"⚠️ Tarjeta Fudo: ${tarjeta:,.0f} vs. TX Klap: ${total_klap:,.0f} → Diferencia: ${diff_card:,.0f}")

    except Exception as e:
        st.error(f"❌ Error al procesar archivos:\n{str(e)}")
