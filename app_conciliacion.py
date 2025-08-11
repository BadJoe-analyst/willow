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
1) Sube los CSV de **Fudo** y **Klap**.  
2) En Fudo, exporta omitiendo las **primeras 3 filas**.  
3) La app detecta la fecha automáticamente desde Fudo (solo **ventas Cerradas**).  
4) **TX Klap** se calcula **sin propinas** y además se muestra el **total de propinas** del día.
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
        # ====== CARGA FUDO (intenta ; y luego ,) ======
        enc_f = detectar_encoding(fudo_file)
        try:
            df_f = pd.read_csv(fudo_file, sep=";", encoding=enc_f, skiprows=3, on_bad_lines="skip")
            if len(df_f.columns) == 1:
                raise ValueError("Separador incorrecto")
        except Exception:
            fudo_file.seek(0)
            df_f = pd.read_csv(fudo_file, sep=",", encoding=enc_f, skiprows=3, on_bad_lines="skip")

        # ====== CARGA KLAP (;) ======
        enc_k = detectar_encoding(klap_file)
        df_k = pd.read_csv(klap_file, sep=";", encoding=enc_k, on_bad_lines="skip")

        # ====== FORMATEO COLUMNAS ======
        # Fudo
        df_f["Fecha"] = pd.to_datetime(df_f["Fecha"], dayfirst=True, errors="coerce")
        df_f["Total"] = pd.to_numeric(df_f["Total"], errors="coerce").fillna(0)
        df_f["Estado"] = df_f["Estado"].astype(str).str.strip().str.lower()

        # Klap
        df_k["Fecha"] = pd.to_datetime(df_k["Fecha"], dayfirst=True, errors="coerce")
        df_k["Monto"]  = pd.to_numeric(df_k["Monto"], errors="coerce").fillna(0)
        df_k["Estado"] = df_k["Estado"].astype(str).str.strip().str.lower()

        # ====== FILTROS ======
        # Fudo: separar Cerradas y En curso
        cerradas     = df_f[df_f["Estado"] == "cerrada"].copy()
        en_curso_df  = df_f[df_f["Estado"] == "en curso"].copy()

        # Klap: solo Aprobado/Aprobada (cualquier variante que contenga 'aproba')
        df_k = df_k[df_k["Estado"].str.contains("aproba", na=False)]

        # ====== KLAP: restar propinas y calcular total de propinas ======
        # Detectar columna de propinas (Propina / Propinas), case-insensitive
        prop_col = next((c for c in df_k.columns if isinstance(c, str) and c.strip().lower() in ["propina", "propinas"]), None)
        if prop_col:
            df_k["Propina_num"] = pd.to_numeric(df_k[prop_col], errors="coerce").fillna(0)
        else:
            df_k["Propina_num"] = 0
        df_k["Monto_neto"] = df_k["Monto"] - df_k["Propina_num"]

        # ====== FECHA DETECTADA DESDE FUDO (CERRADAS) ======
        if cerradas["Fecha"].dropna().empty:
            st.error("❌ No se detectó fecha válida en ventas **Cerradas** de Fudo.")
            st.stop()
        fecha = cerradas["Fecha"].dt.date.mode()[0]
        st.success(f"📅 Fecha detectada: {fecha.strftime('%d-%m-%Y')}")

        # ====== FILTRAR POR FECHA ======
        fudo_dia      = cerradas[cerradas["Fecha"].dt.date == fecha].copy()
        en_curso_dia  = en_curso_df[en_curso_df["Fecha"].dt.date == fecha].copy()
        klap_dia      = df_k[df_k["Fecha"].dt.date == fecha].copy()

        if fudo_dia.empty:
            st.warning("⚠️ No hay ventas **Cerradas** en Fudo para esa fecha.")
        if klap_dia.empty:
            st.warning("⚠️ No hay transacciones **Aprobadas** en Klap para esa fecha.")

        # ====== Categorización de medios (exactos y palabras clave) ======
        def categoriza(m):
            m = str(m).strip().lower()
            if "efectivo" in m: return "Efectivo"
            if "tarj" in m:     return "Tarjeta"
            if "voucher" in m:  return "Voucher"
            if "cta. cte." in m or "cta cte" in m: return "Cta. Cte."
            if "transf" in m:   return "Transferencia"
            return "Otro"

        fudo_dia["Método"]     = fudo_dia["Medio de Pago"].apply(categoriza)
        en_curso_dia["Método"] = en_curso_dia["Medio de Pago"].apply(categoriza)

        # ====== SUMAS (solo CERRADAS para conciliación) ======
        agg = fudo_dia.groupby("Método")["Total"].sum()
        efectivo      = agg.get("Efectivo", 0)
        tarjeta       = agg.get("Tarjeta", 0)
        voucher       = agg.get("Voucher", 0)
        cta_cte       = agg.get("Cta. Cte.", 0)
        transferencia = agg.get("Transferencia", 0)

        # En curso: informativo, NO entra a totales
        total_en_curso = en_curso_dia["Total"].sum()

        # Totales de conciliación
        total_fudo = fudo_dia["Total"].sum()
        total_klap_neto = klap_dia["Monto_neto"].sum()     # sin propina
        total_propinas  = klap_dia["Propina_num"].sum()    # total de propinas del día en Klap
        suma_medios = efectivo + tarjeta + voucher + cta_cte + transferencia

        # ====== TABLA RESUMEN ======
        st.subheader("🔎 Resumen Conciliación")
        df_res = pd.DataFrame([{
            "Cash": efectivo,
            "Card": tarjeta,
            "Voucher": voucher,
            "Cta. Cte.": cta_cte,
            "Transferencia": transferencia,
            "En curso": total_en_curso,                # informativo
            "Propinas Klap": total_propinas,           # nuevo
            "TX Klap (sin propina)": total_klap_neto,  # neto
            "Total Fudo": total_fudo                   # solo cerradas
        }])
        st.dataframe(df_res.style.format("$ {:,.0f}"))
        st.caption("Nota: 'TX Klap (sin propina)' = Monto - Propina. 'Propinas Klap' muestra la suma de propinas del día.")

        # ====== ALERTAS (sin incluir 'En curso') ======
        if abs(total_fudo - suma_medios) > 0:
            diff = total_fudo - suma_medios
            st.error(f"❌ Total Fudo (${total_fudo:,.0f}) ≠ suma medios (${suma_medios:,.0f}) → Δ ${diff:,.0f}")

        if abs(tarjeta - total_klap_neto) > 0:
            diff_card = tarjeta - total_klap_neto
            st.warning(f"⚠️ Tarjeta Fudo (${tarjeta:,.0f}) ≠ Klap sin propina (${total_klap_neto:,.0f}) → Δ ${diff_card:,.0f}")

    except Exception as e:
        st.error(f"❌ Error al procesar archivos:\n{e}")
