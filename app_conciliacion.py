import streamlit as st
import pandas as pd
from datetime import datetime
import chardet

st.set_page_config(page_title="Conciliación Diario Fudo & Klap", layout="centered")

# --- LOGO y TÍTULO ---
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

# --- Subida de archivos ---
fudo_file = st.file_uploader("Archivo Fudo (.csv)", type="csv", key="fudo")
klap_file = st.file_uploader("Archivo Klap (.csv)", type="csv", key="klap")

def detectar_encoding(f):
    raw = f.read()
    f.seek(0)
    return chardet.detect(raw)["encoding"]

if fudo_file and klap_file:
    try:
        # Leer Fudo (sep ; o ,)
        enc_f = detectar_encoding(fudo_file)
        try:
            df_f = pd.read_csv(fudo_file, sep=";", encoding=enc_f, skiprows=3, on_bad_lines="skip")
            if len(df_f.columns) == 1:
                raise ValueError
        except:
            fudo_file.seek(0)
            df_f = pd.read_csv(fudo_file, sep=",", encoding=enc_f, skiprows=3, on_bad_lines="skip")

        # Leer Klap
        enc_k = detectar_encoding(klap_file)
        df_k = pd.read_csv(klap_file, sep=";", encoding=enc_k, on_bad_lines="skip")

        # Formatear fechas y montos
        df_f["Fecha"] = pd.to_datetime(df_f["Fecha"], dayfirst=True, errors="coerce")
        df_f["Total"] = pd.to_numeric(df_f["Total"], errors="coerce").fillna(0)
        df_k["Fecha"] = pd.to_datetime(df_k["Fecha"], dayfirst=True, errors="coerce")
        df_k["Monto"] = pd.to_numeric(df_k["Monto"], errors="coerce").fillna(0)

        # Filtrar Fudo por estado
        df_f["Estado"] = df_f["Estado"].astype(str).str.strip().str.lower()
        cerradas     = df_f[df_f["Estado"] == "cerrada"].copy()
        en_curso_df  = df_f[df_f["Estado"] == "en curso"].copy()

        # Filtrar Klap por aprobado/aprobada
        df_k["Estado"] = df_k["Estado"].astype(str).str.strip().str.lower()
        df_k = df_k[df_k["Estado"].str.contains("aproba")]

        # Detectar fecha dominante en Fudo
        if cerradas["Fecha"].dropna().empty:
            st.error("❌ No se detectó fecha válida en ventas cerradas (Fudo)."); st.stop()
        fecha = cerradas["Fecha"].dt.date.mode()[0]
        st.success(f"📅 Fecha detectada: {fecha.strftime('%d-%m-%Y')}")

        # Filtrar por fecha
        fudo_dia    = cerradas[cerradas["Fecha"].dt.date == fecha].copy()
        en_curso_dia = en_curso_df[en_curso_df["Fecha"].dt.date == fecha].copy()
        klap_dia    = df_k[df_k["Fecha"].dt.date == fecha].copy()

        if fudo_dia.empty:
            st.warning("⚠️ No hay ventas cerradas en Fudo para esa fecha")
        if en_curso_dia.empty:
            st.info("ℹ️ No hay ventas en curso en Fudo para esa fecha")
        if klap_dia.empty:
            st.warning("⚠️ No hay transacciones aprobadas en Klap para esa fecha")

        # Función para categorizar Medio de Pago
        def categoriza(m):
            m = str(m).strip().lower()
            if "efectivo" in m:
                return "Efectivo"
            if "tarj" in m:
                return "Tarjeta"
            if "voucher" in m:
                return "Voucher"
            if "cta. cte." in m:
                return "Cta. Cte."
            if "transf" in m:
                return "Transferencia"
            return "Otro"

        # Agrupar ventas cerradas por método
        fudo_dia["Método"] = fudo_dia["Medio de Pago"].apply(categoriza)
        agg = fudo_dia.groupby("Método")["Total"].sum()
        efectivo      = agg.get("Efectivo", 0)
        tarjeta       = agg.get("Tarjeta", 0)
        voucher       = agg.get("Voucher", 0)
        cta_cte       = agg.get("Cta. Cte.", 0)
        transferencia = agg.get("Transferencia", 0)

        # Sumatorio de en curso (independiente de método)
        total_en_curso = en_curso_dia["Total"].sum()

        # Totales generales
        total_fudo = fudo_dia["Total"].sum()
        total_klap = klap_dia["Monto"].sum()
        suma_medios = efectivo + tarjeta + voucher + cta_cte + transferencia

        # Mostrar resumen
        st.subheader("🔎 Resumen Conciliación")
        resumen = pd.DataFrame([{
            "Cash": efectivo,
            "Card": tarjeta,
            "Voucher": voucher,
            "Cta. Cte.": cta_cte,
            "Transferencia": transferencia,
            "En curso": total_en_curso,
            "Total Fudo": total_fudo,
            "TX Klap": total_klap
        }])
        st.dataframe(resumen.style.format("$ {:,.0f}"))

        # Alertas de diferencia
        if abs(total_fudo - suma_medios) > 0:
            diff = total_fudo - suma_medios
            st.error(f"❌ Total Fudo (${total_fudo:,.0f}) ≠ suma medios (${suma_medios:,.0f}) → Δ ${diff:,.0f}")
        if abs(tarjeta - total_klap) > 0:
            diff_card = tarjeta - total_klap
            st.warning(f"⚠️ Tarjeta Fudo (${tarjeta:,.0f}) ≠ Klap (${total_klap:,.0f}) → Δ ${diff_card:,.0f}")

    except Exception as e:
        st.error(f"❌ Error al procesar archivos:\n{e}")
