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

        # Intentar cargar Fudo con ; primero
        try:
            df_fudo = pd.read_csv(fudo_file, sep=';', encoding=enc_fudo, skiprows=3, on_bad_lines='skip')
            if len(df_fudo.columns) == 1:
                raise ValueError("Separador incorrecto")
        except:
            fudo_file.seek(0)
            df_fudo = pd.read_csv(fudo_file, sep=',', encoding=enc_fudo, skiprows=3, on_bad_lines='skip')

        # Klap fijo con ;
        df_klap = pd.read_csv(klap_file, sep=';', encoding=enc_klap, on_bad_lines='skip')

        # Procesar columnas clave
        df_fudo["Fecha"] = pd.to_datetime(df_fudo["Fecha"], dayfirst=True, errors='coerce')
        df_klap["Fecha"] = pd.to_datetime(df_klap["Fecha"], dayfirst=True, errors='coerce')
        df_fudo["Total"] = pd.to_numeric(df_fudo["Total"], errors='coerce').fillna(0)
        df_klap["Monto"] = pd.to_numeric(df_klap["Monto"], errors='coerce').fillna(0)

        # Filtrar solo registros aprobados en Klap
        df_klap = df_klap[df_klap["Estado"].str.lower().str.strip() == "aprobado"]

        # Detectar fecha
        if df_fudo["Fecha"].dropna().empty:
            st.error("❌ No se detectaron fechas válidas en el archivo Fudo.")
            st.stop()
        fecha_detectada = df_fudo["Fecha"].dropna().dt.date.mode()[0]
        st.success(f"📅 Fecha detectada: {fecha_detectada.strftime('%d-%m-%Y')}")

        # Filtrar por fecha
        fudo_dia = df_fudo[df_fudo["Fecha"].dt.date == fecha_detectada].copy()
        klap_dia = df_klap[df_klap["Fecha"].dt.date == fecha_detectada].copy()

        # Filtrar solo registros cerrados en Fudo
        if "Estado" not in fudo_dia.columns:
            st.error("❌ No se encontró la columna 'Estado' en Fudo.")
            st.stop()
        fudo_dia = fudo_dia[fudo_dia["Estado"].str.strip() == "Cerrada"]

        if fudo_dia.empty:
            st.warning("⚠️ No se encontraron registros cerrados en Fudo para la fecha detectada.")
        if klap_dia.empty:
            st.warning("⚠️ No se encontraron transacciones aprobadas en Klap para la fecha detectada.")

        # Normalizar métodos de pago
        fudo_dia["Medio de Pago Normalizado"] = fudo_dia["Medio de Pago"].replace({
            "Tarj. Débito": "Tarjeta",
            "Tarj Débito": "Tarjeta",
            "Tarj. Crédito": "Tarjeta",
            "Tarjeta Débito": "Tarjeta",
            "Tarj. Crdito": "Tarjeta",
            "Tarj. Dbito": "Tarjeta",
            "Cta. Cte.": "Cuentas Abiertas"
        }).fillna("No Asignado")

        # Agrupar medios
        fudo_agg = fudo_dia.groupby("Medio de Pago Normalizado")["Total"].sum().reset_index()
        fudo_pivot = fudo_agg.pivot_table(index=None, columns="Medio de Pago Normalizado", values="Total", aggfunc="sum").fillna(0)

        for col in ["Efectivo", "Tarjeta", "Transferencia", "Cuentas Abiertas"]:
            if col not in fudo_pivot.columns:
                fudo_pivot[col] = 0

        # Totales
        cash = fudo_pivot["Efectivo"].values[0]
        card = fudo_pivot["Tarjeta"].values[0]
        voucher = fudo_pivot["Transferencia"].values[0]
        abiertos = fudo_pivot["Cuentas Abiertas"].values[0]
        fudo_total = fudo_dia["Total"].sum()
        klap_total = klap_dia["Monto"].sum()
        suma_medios = cash + card + voucher + abiertos

        # Mostrar tabla
        st.subheader("🔎 Resumen Conciliación")
        resumen_df = pd.DataFrame.from_dict({
            "Cash": [cash],
            "Card": [card],
            "Voucher": [voucher],
            "Fudo Pagos": [abiertos],
            "Total Fudo": [fudo_total],
            "TX Klap": [klap_total]
        })
        st.dataframe(resumen_df.style.format("$ {:,.0f}"))

        # Alertas
        diferencia_fudo = fudo_total - suma_medios
        diferencia_card = card - klap_total

        if abs(diferencia_fudo) > 0:
            st.error(f"⚠️ Total Fudo: ${fudo_total:,.0f} vs. suma de medios: ${suma_medios:,.0f} → Diferencia: ${diferencia_fudo:,.0f}")

        if abs(diferencia_card) > 0:
            st.warning(f"⚠️ Tarjeta Fudo: ${card:,.0f} vs. Klap: ${klap_total:,.0f} → Diferencia: ${diferencia_card:,.0f}")

    except Exception as e:
        st.error(f"❌ Error al procesar archivos:\n{str(e)}")
