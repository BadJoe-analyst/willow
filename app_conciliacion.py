import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Conciliación Diario Fudo & Klap", layout="centered")

# === LOGO ===
st.image("https://github.com/BadJoe-analyst/willow/blob/main/logo.jpeg", width=200)

st.title("📊 Conciliación de Ventas: Fudo vs Klap")

st.markdown("""
### 📌 Instrucciones:
1. Asegúrate de tener **dos archivos en formato CSV**:
   - El primero debe ser exportado desde Fudo (omite las primeras 3 filas al guardar)
   - El segundo debe ser exportado desde Klap
2. No importa el nombre de los archivos, pero deben contener las columnas esperadas.
3. Esta app detecta automáticamente la fecha contenida en el archivo de Fudo.
4. Los archivos deben contener datos válidos del mismo día.
""")

# === CARGA DE ARCHIVOS ===
subidos = st.file_uploader("📎 Sube dos archivos CSV (Fudo y Klap)", type=["csv"], accept_multiple_files=True)

if subidos and len(subidos) == 2:
    try:
        # Detectar cuál es Fudo por columnas típicas
        df1 = pd.read_csv(subidos[0], sep=';', encoding='latin1', skiprows=3, on_bad_lines='skip')
        df2 = pd.read_csv(subidos[1], sep=';', encoding='utf-8', on_bad_lines='skip')

        if "Medio de Pago" in df1.columns:
            df_fudo, df_klap = df1, df2
        elif "Medio de Pago" in df2.columns:
            df_fudo, df_klap = df2, df1
        else:
            st.error("❌ No se pudo identificar cuál archivo es Fudo. Asegúrate de subir un archivo válido exportado desde Fudo.")
            st.stop()

        # Procesar fechas y montos
        df_fudo["Fecha"] = pd.to_datetime(df_fudo["Fecha"], dayfirst=True, errors='coerce')
        df_fudo["Total"] = pd.to_numeric(df_fudo["Total"], errors='coerce').fillna(0)
        df_klap["Fecha"] = pd.to_datetime(df_klap["Fecha"], dayfirst=True, errors='coerce')
        df_klap["Monto"] = pd.to_numeric(df_klap["Monto"], errors='coerce').fillna(0)

        if df_fudo["Fecha"].dropna().empty:
            st.error("❌ No se pudo detectar ninguna fecha válida en el archivo Fudo.")
            st.stop()

        # Detectar fecha automáticamente
        fecha_detectada = df_fudo["Fecha"].dropna().dt.date.mode()[0]
        st.success(f"📅 Fecha detectada: {fecha_detectada.strftime('%d-%m-%Y')}")

        # Filtrar por fecha
        fudo_dia = df_fudo[df_fudo["Fecha"].dt.date == fecha_detectada].copy()
        klap_dia = df_klap[df_klap["Fecha"].dt.date == fecha_detectada].copy()

        if fudo_dia.empty:
            st.warning("⚠️ No se encontraron registros en Fudo para la fecha detectada.")
        if klap_dia.empty:
            st.warning("⚠️ No se encontraron registros en Klap para la fecha detectada.")

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
            st.error(f"⚠️ Total Fudo: ${fudo_total:,.0f}\nSuma de medios de pago: ${suma_medios:,.0f}\n→ ❌ Hay una diferencia entre el total y los medios de pago.")

        if abs(card - klap_total) > 0:
            st.warning(f"⚠️ Tarjeta Fudo: ${card:,.0f}\nTX Klap: ${klap_total:,.0f}\n→ ⚠️ Hay una diferencia entre el monto en tarjeta Fudo y Klap.")

    except Exception as e:
        st.error(f"❌ Error al procesar archivos:\n{str(e)}")
