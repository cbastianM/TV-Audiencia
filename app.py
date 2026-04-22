import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Canal 8 - Análisis de Audiencia", page_icon="📺", layout="wide")

st.title("📺 Canal 8 - Análisis de Audiencia TV")

DEDUP_WINDOW_MIN = 60
COL_MAP = {
    "Marca temporal": "timestamp",
    "correo": "email",
    "Nombre completo": "name",
    "Numero de WhatsApp": "whatsapp",
    "Ciudad/municipio": "city",
}

st.sidebar.header("📂 Cargar datos")
uploaded_file = st.sidebar.file_uploader("Sube tu archivo CSV o Excel", type=["csv", "xlsx", "xls"])

if uploaded_file is None:
    st.info("👆 Sube un archivo CSV o Excel para comenzar el análisis.")
    st.stop()

@st.cache_data
def load_data(file):
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    else:
        return pd.read_excel(file)

df_raw = load_data(uploaded_file)
st.sidebar.success(f"Archivo cargado: {len(df_raw)} registros")

df = df_raw.rename(columns=COL_MAP)
for c in ["timestamp", "email", "name", "whatsapp", "city"]:
    if c not in df.columns:
        df[c] = None

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df["email"] = df["email"].astype(str).str.strip().str.lower()
df["name"] = df["name"].astype(str).str.strip().str.title()
df["whatsapp"] = df["whatsapp"].astype(str).str.replace(r"\D", "", regex=True)
df["city"] = df["city"].astype(str).str.strip().str.title()

df = df.dropna(subset=["timestamp"])

df = df.sort_values(["email", "timestamp"]).reset_index(drop=True)

def mark_dups_for_column(df, key_col, window_minutes):
    valid_mask = df[key_col].notna() & (df[key_col] != "None") & (df[key_col] != "") & (df[key_col] != "nan")
    valid_df = df[valid_mask].copy()
    if len(valid_df) == 0:
        return pd.Series(False, index=df.index)

    is_dup = pd.Series(False, index=df.index)
    for key, group in valid_df.groupby(key_col):
        group = group.sort_values("timestamp")
        times = group["timestamp"].values
        indices = group.index.tolist()
        for i in range(1, len(times)):
            diff = (times[i] - times[i - 1]) / np.timedelta64(1, "m")
            if diff <= window_minutes:
                is_dup.iloc[indices[i]] = True
    return is_dup

df["is_duplicate"] = mark_dups_for_column(df, "email", DEDUP_WINDOW_MIN)
df_unique = df[~df["is_duplicate"]].copy()
df_unique["hour"] = df_unique["timestamp"].dt.hour
df_unique["date"] = df_unique["timestamp"].dt.date
df_unique["day_name"] = df_unique["timestamp"].dt.day_name()

tab_overview, tab_time, tab_duplicates, tab_raw = st.tabs([
    "📊 Resumen", "⏱️ Serie Temporal", "🔍 Duplicados", "📋 Datos"
])

with tab_overview:
    st.subheader("KPIs de Audiencia")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total registros", f"{len(df):,}")
    c2.metric("Duplicados detectados", f"{df['is_duplicate'].sum():,}")
    c3.metric("Audiencia única", f"{len(df_unique):,}")
    c4.metric("Ciudades / municipios", df_unique["city"].nunique())
    c5.metric("Rango de fechas", f"{(df_unique['timestamp'].max() - df_unique['timestamp'].min()).days} días")

    st.markdown("---")
    st.subheader("Filtrar por Horario")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        hour_start = st.slider("Hora inicio", 0, 23, 0)
    with col_f2:
        hour_end = st.slider("Hora fin", 0, 23, 23)

    mask = (df_unique["hour"] >= hour_start) & (df_unique["hour"] <= hour_end)
    df_filtered = df_unique[mask].copy()

    c1, c2, c3 = st.columns(3)
    c1.metric("Audiencia en horario", f"{len(df_filtered):,}")
    c2.metric(f"% del total ({hour_start}:00 - {hour_end}:00)", f"{len(df_filtered)/len(df_unique)*100:.1f}%")
    c3.metric("Horarios picos", f"{df_filtered['hour'].value_counts().idxmax()}:00")

    st.markdown("---")
    st.subheader("Audiencia por Hora del Día")
    hour_counts = df_filtered["hour"].value_counts().sort_index().reset_index()
    hour_counts.columns = ["Hora", "Audiencia"]

    fig_area = go.Figure()
    fig_area.add_trace(go.Scatter(
        x=hour_counts["Hora"], y=hour_counts["Audiencia"],
        mode="lines+markers", fill="tozeroy",
        line=dict(color="#1f77b4", width=3),
        marker=dict(size=8),
        name="Audiencia"
    ))
    fig_area.update_layout(
        xaxis_title="Hora del día",
        yaxis_title="Audiencia única",
        xaxis=dict(tickmode="linear", tick0=0, dtick=1),
        margin=dict(l=0, r=0, t=20, b=40),
        hovermode="x unified"
    )
    st.plotly_chart(fig_area, use_container_width=True)

    st.subheader("Distribución de Audiencia por Franja Horaria")
    bins = [(0, 5, "Madrugada (0-5)"), (6, 11, "Mañana (6-11)"),
            (12, 17, "Tarde (12-17)"), (18, 23, "Noche (18-23)")]
    labels = [label for _, _, label in bins]

    def get_bracket(h):
        for start, end, label in bins:
            if start <= h <= end:
                return label
        return label

    df_filtered = df_filtered.copy()
    df_filtered["franja"] = df_filtered["hour"].apply(get_bracket)
    franja_counts = df_filtered["franja"].value_counts().reindex(labels).reset_index()
    franja_counts.columns = ["Franja", "Audiencia"]

    fig_franja = px.bar(franja_counts, x="Franja", y="Audiencia", text="Audiencia",
                        color="Audiencia", color_continuous_scale="Blues")
    fig_franja.update_layout(margin=dict(l=0, r=0, t=20, b=40), xaxis_tickangle=-20)
    st.plotly_chart(fig_franja, use_container_width=True)

    st.subheader("Lista de Audiencia por Ciudad")
    city_list = df_filtered[["city"]].copy()
    city_list = city_list[city_list["city"].notna() & (city_list["city"] != "None") & (city_list["city"] != "nan") & (city_list["city"] != "")]
    city_list.columns = ["Ciudad / Municipio"]
    st.dataframe(city_list.sort_values("Ciudad / Municipio").reset_index(drop=True),
                 use_container_width=True, hide_index=True)

with tab_time:
    st.subheader("Evolución de Audiencia en el Tiempo")

    col_g1, col_g2 = st.columns([1, 3])
    with col_g1:
        granularity = st.selectbox("Granularidad", ["Diaria", "Semanal", "Mensual"])
    with col_g2:
        st.write("")

    if granularity == "Diaria":
        df_unique["period_label"] = df_unique["timestamp"].dt.strftime("%Y-%m-%d")
        df_unique["period_dt"] = pd.to_datetime(df_unique["period_label"])
    elif granularity == "Semanal":
        df_unique["period_label"] = df_unique["timestamp"].dt.to_period("W").astype(str)
        df_unique["period_dt"] = df_unique["timestamp"].dt.to_period("W").apply(lambda x: x.start_time)
    else:
        df_unique["period_label"] = df_unique["timestamp"].dt.to_period("M").astype(str)
        df_unique["period_dt"] = df_unique["timestamp"].dt.to_period("M").apply(lambda x: x.start_time)

    ts = df_unique.groupby("period_label", as_index=False).agg(
        audiencia=("period_label", "size"),
        period_dt=("period_dt", "first")
    ).sort_values("period_dt").reset_index(drop=True)

    fig_ts = px.bar(ts, x="period_label", y="audiencia",
                    color="audiencia", color_continuous_scale="Blues",
                    text="audiencia")
    fig_ts.update_layout(
        xaxis_title="Fecha", yaxis_title="Audiencia única",
        margin=dict(l=0, r=0, t=20, b=50),
        coloraxis_showscale=False
    )
    st.plotly_chart(fig_ts, use_container_width=True)

    st.subheader("Estadísticas de la Serie")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Promedio", f"{ts['audiencia'].mean():.1f}")
    c2.metric("Máximo", f"{ts['audiencia'].max():,}")
    c3.metric("Mediana", f"{ts['audiencia'].median():.1f}")
    c4.metric("Desv. estándar", f"{ts['audiencia'].std():.1f}")

    st.markdown("---")
    st.subheader("Audiencia por Día de la Semana")
    day_order_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    day_map = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
               "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo"}

    df_unique = df_unique.copy()
    df_unique["day_es"] = df_unique["day_name"].map(day_map)
    day_counts = df_unique["day_es"].value_counts().reindex(day_order_es).reset_index()
    day_counts.columns = ["Día", "Audiencia"]

    fig_days = px.bar(day_counts, x="Día", y="Audiencia", text="Audiencia",
                      color="Audiencia", color_continuous_scale="Viridis")
    fig_days.update_layout(margin=dict(l=0, r=0, t=20, b=40))
    st.plotly_chart(fig_days, use_container_width=True)

with tab_duplicates:
    st.subheader("Análisis de Registros Duplicados")
    c1, c2 = st.columns(2)
    c1.metric("Total registros", f"{len(df):,}")
    c2.metric("Duplicados eliminados", f"{df['is_duplicate'].sum():,}")

    dup_df = df[df["is_duplicate"]].copy()
    if len(dup_df) > 0:
        st.subheader("Registros duplicados detectados")
        dup_df["timestamp"] = dup_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        st.dataframe(dup_df[["timestamp", "name", "email", "whatsapp", "city"]].head(100),
                     use_container_width=True, hide_index=True)
    else:
        st.success("No se detectaron duplicados con la configuración actual.")

    st.subheader("Lista de Duplicados por Ciudad")
    dup_by_city = dup_df["city"].value_counts().reset_index() if len(dup_df) > 0 else pd.DataFrame()
    if len(dup_by_city) > 0:
        dup_by_city.columns = ["Ciudad", "Duplicados"]
        dup_by_city = dup_by_city[dup_by_city["Ciudad"] != "None"]
        st.dataframe(dup_by_city, use_container_width=True, hide_index=True)

with tab_raw:
    st.subheader("Datos Limpios (sin duplicados)")
    df_display = df_unique.copy()
    df_display["timestamp"] = df_display["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    st.dataframe(df_display[["timestamp", "name", "email", "whatsapp", "city"]],
                 use_container_width=True, hide_index=True)

    csv = df_display.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 Descargar datos limpios (CSV)", csv, "audiencia_limpia.csv", "text/csv")
