      # Cargar Fudo (intenta ; y luego ,)
      try:
          df_fudo = pd.read_csv(fudo_file, sep=';', encoding=enc_fudo, skiprows=3, on_bad_lines='skip')
          if len(df_fudo.columns) == 1:
              raise ValueError("Separador incorrecto detectado")
      except:
          fudo_file.seek(0)
          df_fudo = pd.read_csv(fudo_file, sep=',', encoding=enc_fudo, skiprows=3, on_bad_lines='skip')

      # Klap siempre con ;
      df_klap = pd.read_csv(klap_file, sep=';', encoding=enc_klap, on_bad_lines='skip')

      # Limpiar columnas relevantes
      df_fudo["Fecha"] = pd.to_datetime(df_fudo["Fecha"], dayfirst=True, errors='coerce')
      df_fudo["Total"] = pd.to_numeric(df_fudo["Total"], errors='coerce').fillna(0)
      df_klap["Fecha"] = pd.to_datetime(df_klap["Fecha"], dayfirst=True, errors='coerce')
      df_klap["Monto"] = pd.to_numeric(df_klap["Monto"], errors='coerce').fillna(0)

      # Detectar fecha
      if df_fudo["Fecha"].dropna().empty:
          st.error("❌ No se detectó ninguna fecha válida en el archivo Fudo.")
          st.stop()
      fecha_detectada = df_fudo["Fecha"].dropna().dt.date.mode()[0]
      st.success(f"📅 Fecha detectada: {fecha_detectada.strftime('%d-%m-%Y')}")

      # Filtrar registros
      fudo_dia = df_fudo[df_fudo["Fecha"].dt.date == fecha_detectada].copy()
      klap_dia = df_klap[df_klap["Fecha"].dt.date == fecha_detectada].copy()

      # Filtro: solo cerradas
      fudo_dia = fudo_dia[fudo_dia["Estado"].astype(str).str.strip().str.lower() == "cerrada"]

      # Filtro: solo transacciones aprobadas (robusto)
      klap_dia = klap_dia[klap_dia["Estado"].astype(str).str.strip().str.lower().str.startswith("aproba")]

      # Diagnóstico si no hay registros
      if fudo_dia.empty:
          fechas_disponibles = df_fudo[df_fudo["Estado"].astype(str).str.strip().str.lower() == "cerrada"]["Fecha"].dropna().dt.date.unique()
          st.warning(f"⚠️ No se encontraron registros **cerrados** en Fudo para la fecha detectada.\nFechas con estado 'Cerrada': {list(fechas_disponibles)}")

      if klap_dia.empty:
          fechas_klap = df_klap["Fecha"].dropna().dt.date.unique()
          st.warning(f"⚠️ No se encontraron transacciones **aprobadas** en Klap para la fecha detectada.\nFechas con transacciones en Klap: {list(fechas_klap)}")

      if fudo_dia.empty or klap_dia.empty:
          st.stop()

      # Normalizar pagos
      fudo_dia["Medio de Pago Normalizado"] = fudo_dia["Medio de Pago"].replace({
          "Tarj. Dbito": "Tarjeta",
          "Tarj. Débito": "Tarjeta",
          "Tarj. Crédito": "Tarjeta",
          "Tarj. Crdito": "Tarjeta",
          "Tarj Débito": "Tarjeta",
          "Tarjeta Débito": "Tarjeta",
          "Cta. Cte.": "Cuentas Abiertas",
          "Cta Cte": "Cuentas Abiertas",
          "Cta Corriente": "Cuentas Abiertas"
      }).fillna("No Asignado")

      # Agrupar
      fudo_agg = fudo_dia.groupby("Medio de Pago Normalizado")["Total"].sum().reset_index()
      fudo_pivot = fudo_agg.pivot_table(index=None, columns="Medio de Pago Normalizado", values="Total", aggfunc="sum").fillna(0)

      for col in ["Efectivo", "Tarjeta", "Transferencia", "Cuentas Abiertas"]:
          if col not in fudo_pivot.columns:
              fudo_pivot[col] = 0

      cash = fudo_pivot["Efectivo"].values[0]
      card = fudo_pivot["Tarjeta"].values[0]
      voucher = fudo_pivot["Transferencia"].values[0]
      abiertos = fudo_pivot["Cuentas Abiertas"].values[0]
      fudo_total = fudo_dia["Total"].sum()
      klap_total = klap_dia["Monto"].sum()
      suma_medios = cash + card + voucher + abiertos

      # Mostrar resumen
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
      diferencia_total = fudo_total - suma_medios
      diferencia_tarjeta = card - klap_total

      if abs(diferencia_total) > 0:
          st.error(f"❌ Diferencia entre Total Fudo y suma de medios de pago: ${diferencia_total:,.0f}")

      if abs(diferencia_tarjeta) > 0:
          st.warning(f"⚠️ Diferencia entre Tarjeta Fudo (${card:,.0f}) y Klap (${klap_total:,.0f}): ${diferencia_tarjeta:,.0f}")

  except Exception as e:
      st.error(f"❌ Error al procesar archivos:\n{str(e)}")
