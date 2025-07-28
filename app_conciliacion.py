import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Conciliación Diario Fudo & Klap", layout="centered")
st.title("📊 Conciliación de Ventas: Fudo vs Klap")

st.markdown("""
### 📌 Instrucciones:
1. Asegúrate de tener **dos archivos en formato CSV**:
   - `ventas.csv`: exportado desde Fudo (omite las primeras 3 filas al guardar)
   - `transacciones.csv`: exportado desde Klap
2. Ambos archivos deben tener el nombre correcto al momento de subirlos.
3. Esta app detecta automáticamente la fecha contenida en el archivo de Fudo.
4. Los archivos deben contener datos válidos del mismo día.
""")

# === CARGA DE ARCHIVOS ===
fudo_file = st.file_uploader("📎 Archivo Fudo (ventas.csv)", type=["csv"])
klap_file = st.file_uploader("📎 Archivo Klap (transacciones.csv)", type=["csv"])

if fudo_file and klap_file:
    try:
        # Leer Fudo (saltando las 3 primeras filas)
        df_fudo = pd.read_csv(fudo_file, sep=';', encoding='latin1', skiprows=3)
        df_klap = pd.read_csv(klap_file, sep=';', encoding='utf-8')

        # Procesar fechas y montos
        df_fudo["Fecha"] = pd.to_datetime(df_fudo["Fecha"], dayfirst=True, errors='coerce')
        df_fudo["Total"] = pd.to_numeric(df_fudo["Total"], errors='coerce').fillna(0)
        df_klap["Fecha"] = pd.to_datetime(df_klap["Fecha"], dayfirst=True, errors='coerce')
        df_klap["Monto"] = pd.to_numeric(df_klap["Monto"], errors='coerce').fillna(0)

        # Detectar fecha automáticamente
        fecha_detectada = df_fudo["Fecha"].dropna().dt.date.mode()[0]
        st.success(f"📅 Fecha detectada: {fecha_detectada.strftime('%d-%m-%Y')}")

        # Filtrar
        fudo_dia = df_fudo[df_fudo["Fecha"].dt.date == fecha_detectada].copy()
        klap_dia = df_klap[df_klap["Fecha"].dt.date == fecha_detectada].copy()

        # Normalizar métodos de pago
        fudo_dia["Medio de Pago Normalizado"] = fudo_dia["Medio de Pago"].replace({
            "Tarj. Dbito": "Tarjeta",
            "Tarj. Débito": "Tarjeta",
            "Tarj. Crédito": "Tarjeta",
            "Tarj. Crdito": "Tarjeta",
            "Tarj Débito": "Tarjeta",
            "Tarjeta Débito": "Tarjeta"
        }).fillna("No Asignado")

        # Agrupar
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
        if abs(fudo_total - suma_medios) > 0:
            st.error(f"⚠️ Total Fudo (${fudo_total:,.0f}) no cuadra con la suma por medios (${suma_medios:,.0f})")

        if abs(card - klap_total) > 0:
            st.warning(f"⚠️ Monto en tarjeta Fudo (${card:,.0f}) no coincide con TX Klap (${klap_total:,.0f})")

    except Exception as e:
        st.error(f"❌ Error al procesar archivos: {e}")
