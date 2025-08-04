import streamlit as st
import pandas as pd
from datetime import datetime
import chardet

st.set_page_config(page_title="Conciliación Diario Fudo & Klap", layout="centered")

# === LOGO + TÍTULO ===
st.markdown("""
<div style="text-align: center;">
  <img src="https://raw.githubusercontent.com/BadJoe-analyst/willow/main/logo.jpeg" width="200"/>
  <h2 style="margin-top: 0;">Willow Café</h2>
</div>
""", unsafe_allow_html=True)
st.title("📊 Conciliación de Ventas: Fudo vs Klap")

st.markdown("""
### 📌 Instrucciones:
1. Sube los CSV de Fudo y Klap.
2. Fudo: omite las primeras 3 filas al exportar.
3. La app detecta la fecha automáticamente.
""")

st.subheader("⬆️ Subida de archivos")
fudo_file = st.file_uploader("Archivo Fudo (.csv)", type="csv", key="fudo")
klap_file = st.file_uploader("Archivo Klap (.csv)", type="csv", key="klap")

def detectar_encoding(f):
    raw = f.read()
    f.seek(0)
    return chardet.detect(raw)["encoding"]

if fudo_file and klap_file:
    try:
        # detectar encodings
        enc_f = detectar_encoding(fudo_file)
        enc_k = detectar_encoding(klap_file)

        # cargar Fudo (sep ; o ,)
        try:
            df_f = pd.read_csv(fudo_file, sep=";", encoding=enc_f, skiprows=3, on_bad_lines="skip")
            if len(df_f.columns)==1: raise
        except:
            fudo_file.seek(0)
            df_f = pd.read_csv(fudo_file, sep=",", encoding=enc_f, skiprows=3, on_bad_lines="skip")

        # cargar Klap
        df_k = pd.read_csv(klap_file, sep=";", encoding=enc_k, on_bad_lines="skip")

        # parsear fechas y montos
        df_f["Fecha"] = pd.to_datetime(df_f["Fecha"], dayfirst=True, errors="coerce")
        df_f["Total"] = pd.to_numeric(df_f["Total"], errors="coerce").fillna(0)
        df_k["Fecha"] = pd.to_datetime(df_k["Fecha"], dayfirst=True, errors="coerce")
        df_k["Monto"] = pd.to_numeric(df_k["Monto"], errors="coerce").fillna(0)

        # filtrar Klap aprobado/aprobada
        df_k["Estado"] = df_k["Estado"].astype(str).str.strip().str.lower()
        df_k = df_k[df_k["Estado"].str.contains("aproba")]

        # filtrar Fudo cerrada
        df_f["Estado"] = df_f["Estado"].astype(str).str.strip().str.lower()
        df_f = df_f[df_f["Estado"]=="cerrada"]

        # asegurarnos hay fecha
        if df_f["Fecha"].dropna().empty:
            st.error("❌ No se encontró fecha válida en Fudo."); st.stop()
        fecha = df_f["Fecha"].dt.date.mode()[0]
        st.success(f"📅 Fecha: {fecha.strftime('%d-%m-%Y')}")

        # filtrar ambos por fecha
        fudo_dia = df_f[df_f["Fecha"].dt.date==fecha].copy()
        klap_dia= df_k[df_k["Fecha"].dt.date==fecha].copy()

        if fudo_dia.empty:
            st.warning("⚠️ No hay ventas cerradas en Fudo para esa fecha")
        if klap_dia.empty:
            st.warning("⚠️ No hay transacciones aprobadas en Klap para esa fecha")

        # función de normalización por palabras clave
        def categoriza(m):
            m = str(m).strip().lower()
            if "efectivo" in m:
                return "Efectivo"
            if "tarj" in m:
                return "Tarjeta"
            if "vouch" in m or "transf" in m:
                return "Transferencia"
            if "cta" in m or "corrient" in m or "cxc" in m:
                return "Cuentas Abiertas"
            return "Otro"

        fudo_dia["Método"] = fudo_dia["Medio de Pago"].apply(categoriza)

        # agrupar
        agg = fudo_dia.groupby("Método")["Total"].sum()
        cash = agg.get("Efectivo", 0)
        card = agg.get("Tarjeta", 0)
        voucher= agg.get("Transferencia", 0)
        cta   = agg.get("Cuentas Abiertas", 0)
        total_fudo = fudo_dia["Total"].sum()
        total_klap = klap_dia["Monto"].sum()
        suma_medios = cash+card+voucher+cta

        # mostrar
        df_res = pd.DataFrame([{
            "Cash": cash,
            "Card": card,
            "Voucher": voucher,
            "Fudo Pagos": cta,
            "Total Fudo": total_fudo,
            "TX Klap": total_klap
        }])
        st.subheader("🔎 Resumen Conciliación")
        st.dataframe(df_res.style.format("$ {:,.0f}"))

        # alertas
        if total_fudo!=suma_medios:
            st.error(f"❌ Fudo total ${total_fudo:,.0f} ≠ suma medios ${suma_medios:,.0f} → Δ ${total_fudo-suma_medios:,.0f}")
        if card!=total_klap:
            st.warning(f"⚠️ Fudo tarjeta ${card:,.0f} ≠ Klap ${total_klap:,.0f} → Δ ${card-total_klap:,.0f}")

    except Exception as e:
        st.error(f"❌ Error: {e}")
