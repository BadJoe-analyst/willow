import streamlit as st
import pandas as pd
from datetime import datetime
import chardet

st.set_page_config(page_title="Conciliación Diario Fudo & Klap", layout="centered")

# === LOGO Y TÍTULO ===
st.markdown("""
<div style="text-align: center;">
    <img src="https://raw.githubusercontent.com/BadJoe-analyst/willow/main/logo.jpeg" width="200"/>
    <h2 style="margin-top: 0;">Willow Café</h2>
</div>
""", unsafe_allow_html=True)

st.title("📊 Conciliación de Ventas: Fudo vs Klap")

st.markdown("""
### 📌 Instrucciones:
1. Sube los archivos exportados de Fudo y Klap en formato CSV.
2. El archivo de Fudo debe omitir manualmente las primeras 3 filas antes de exportar.
3. Esta app detecta automáticamente la fecha contenida en el archivo de Fudo.
""")

# === SUBIDA DE ARCHIVOS ===
st.subheader("⬆️ Subida de archivos")
fudo_file = st.file_uploader("Archivo Fudo (.csv)", type=["csv"], key="fudo")
klap_file = st.file_uploader("Archivo Klap (.csv)", type=["csv"], key="klap")

def detectar_encoding(file):
    raw = file.read()
    file.seek(0)
    return chardet.detect(raw)['encoding']

if fudo_file and klap_file:
    try:
        enc_fudo = detectar_encoding(fudo_file)
        enc_klap = detectar_encoding(klap_file)

        # === CARGAR FUDO ===
        try:
            df_fudo = pd.read_csv(fudo_file, sep=';', encoding=enc_fudo, skiprows=3, on_bad_lines='skip')
            if len(df_fudo.columns) == 1:
                raise ValueError
        except:
            fudo_file.seek(0)
            df_fudo = pd.read_csv(fudo_file, sep=',', encoding=enc_fudo, skiprows=3, on_bad_lines='skip')

        # === CARGAR KLAP ===
        df_klap = pd.read_csv(klap_file, sep=';', encoding=enc_klap, on_bad_lines='skip')

        # === FILTRO APROBADOS EN KLAP ===
        estado_aprobado = next((e for e in df_klap["Estado"].dropna().astype(str).str.lower().unique() if "aproba" in e), None)
        df_klap = df_klap[df_klap["Estado"].str.lower() == estado_aprobado] if estado_aprobado else df_klap.iloc[0:0]

        # === FECHAS Y MONTO ===
        df_fudo["Fecha"] = pd.to_datetime(df_fudo["Fecha"], dayfirst=True, errors='coerce')
        df_klap["Fecha"] = pd.to_datetime(df_klap["Fecha"], dayfirst=True, errors='coerce')
        df_fudo["Total"] = pd.to_numeric(df_fudo["Total"], errors='coerce').fillna(0)
        df_klap["Monto"] = pd.to_numeric(df_klap["Monto"], errors='coerce').fillna(0)

        # === FILTRO ESTADO CERRADA EN FUDO ===
        if "Estado" in df_fudo.columns:
            df_fudo = df_fudo[df_fudo["Estado"].str.lower().str.contains("cerrad")]

        if df_fudo["Fecha"].dropna().empty:
            st.error("❌ No se encontró fecha válida en archivo Fudo.")
            st.stop()

        fecha_detectada = df_fudo["Fecha"].dropna().dt.date.mode()[0]
        st.success(f"📅 Fecha detectada: {fecha_detectada.strftime('%d-%m-%Y')}")

        fudo_dia = df_fudo[df_fudo["Fecha"].dt.date == fecha_detectada].copy()
        klap_dia = df_klap[df_klap["Fecha"].dt.date == fecha_detectada].copy()

        if fudo_dia.empty:
            st.warning("⚠️ No se encontraron registros cerrados en Fudo para la fecha detectada.")
        if klap_dia.empty:
            st.warning("⚠️ No se encontraron transacciones aprobadas en Klap para la fecha detectada.")

        # === NORMALIZAR MÉTODOS DE PAGO ===
        fudo_dia["Medio de Pago Normalizado"] = fudo_dia["Medio de Pago"].replace({
            "Tarj. Débito": "Tarjeta",
            "Tarj Débito": "Tarjeta",
            "Tarjeta Débito": "Tarjeta",
            "Tarj. Crédito": "Tarjeta",
            "Tarj. Crdito": "Tarjeta",
            "Transferencia": "Transferencia",
            "Cta Corriente": "Cuentas Abiertas",
            "Cta. Corriente": "Cuentas Abiertas",
        }).fillna("No Asignado")

        # === AGRUPACIÓN ===
        fudo_agg = fudo_dia.groupby("Medio de Pago Normalizado")["Total"].sum().reset_index()
        pivot = fudo_agg.pivot_table(index=None, columns="Medio de Pago Normalizado", values="Total", aggfunc="sum").fillna(0)
        for metodo in ["Efectivo", "Tarjeta", "Transferencia", "Cuentas Abiertas"]:
            if metodo not in pivot.columns:
                pivot[metodo] = 0

        # === TOTALES ===
        cash = pivot["Efectivo"].values[0]
        card = pivot["Tarjeta"].values[0]
        voucher = pivot["Transferencia"].values[0]
        abiertos = pivot["Cuentas Abiertas"].values[0]
        fudo_total = fudo_dia["Total"].sum()
        klap_total = klap_dia["Monto"].sum()
        suma_medios = cash + card + voucher + abiertos

        # === RESUMEN ===
        st.subheader("🔎 Resumen Conciliación")
        resumen = pd.DataFrame({
            "Cash": [cash],
            "Card": [card],
            "Voucher": [voucher],
            "Fudo Pagos": [abiertos],
            "Total Fudo": [fudo_total],
            "TX Klap": [klap_total]
        })
        st.dataframe(resumen.style.format("$ {:,.0f}"))

        # === ALERTAS ===
        if abs(fudo_total - suma_medios) > 0:
            dif = fudo_total - suma_medios
            st.error(f"❌ Total Fudo: ${fudo_total:,.0f} | Medios: ${suma_medios:,.0f} → Diferencia: ${dif:,.0f}")
        if abs(card - klap_total) > 0:
            dif_card = card - klap_total
            st.warning(f"⚠️ Tarjeta Fudo: ${card:,.0f} | TX Klap: ${klap_total:,.0f} → Diferencia: ${dif_card:,.0f}")

    except Exception as e:
        st.error(f"❌ Error al procesar archivos:\n{str(e)}")
