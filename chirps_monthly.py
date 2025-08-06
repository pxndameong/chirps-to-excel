import streamlit as st
import requests
import rasterio
import numpy as np
import pandas as pd
from datetime import datetime
import plotly.express as px
import os
import io

# --- Konfigurasi Aplikasi Streamlit ---
st.set_page_config(
    page_title="CHIRPS Data Downloader & Viewer",
    layout="wide",
    initial_sidebar_state="auto"
)

# --- Judul Aplikasi ---
st.title("🌧️ CHIRPS Data Downloader & Viewer")
st.markdown("Aplikasi ini memungkinkan Anda mengunduh, memproses, dan memvisualisasikan data curah hujan bulanan CHIRPS v3.0.")

# --- Pengaturan Tahun & Bulan Range ---
TAHUN_MULAI = 1981
TAHUN_AKHIR = datetime.now().year

# --- Input Pengguna di Sidebar ---
st.sidebar.header("Pilih Parameter Data")

selected_year = st.sidebar.selectbox(
    "Pilih Tahun:",
    options=list(range(TAHUN_MULAI, TAHUN_AKHIR + 1)),
    index=len(range(TAHUN_MULAI, TAHUN_AKHIR + 1)) - 1
)

selected_month_num = st.sidebar.selectbox(
    "Pilih Bulan:",
    options=[(f"{m:02d}", datetime(2000, m, 1).strftime('%B')) for m in range(1, 13)],
    format_func=lambda x: x[1],
    index=datetime.now().month - 1
)[0]

# Opsi untuk ukuran titik
point_size_mode = st.sidebar.radio(
    "Ukuran Titik Peta:",
    ('Konsisten', 'Dinamis (berdasarkan curah hujan)'),
    horizontal=True
)

st.sidebar.markdown("---")
st.sidebar.header("Atur Batas Geografis")

col1, col2 = st.sidebar.columns(2)
with col1:
    lat_min = st.number_input("Latitude Min:", value=-9.0, step=0.1, format="%.1f")
    lon_min = st.number_input("Longitude Min:", value=104.0, step=0.1, format="%.1f")
with col2:
    lat_max = st.number_input("Latitude Max:", value=-5.5, step=0.1, format="%.1f")
    lon_max = st.number_input("Longitude Max:", value=115.0, step=0.1, format="%.1f")

# --- Fungsi untuk Mengunduh dan Memproses Data ---
@st.cache_data(ttl=3600)
def get_chirps_data(year, month, lat_min, lat_max, lon_min, lon_max):
    """
    Mengunduh data CHIRPS, memprosesnya, dan mengembalikan DataFrame.
    """
    file_name = f"chirps-v3.0.{year}.{month}"
    url = f"https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/global/tifs/{file_name}.tif"

    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        tif_in_memory = io.BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            tif_in_memory.write(chunk)
        tif_in_memory.seek(0)

        with rasterio.open(tif_in_memory) as src:
            band_data = src.read(1)
            band_data = np.where(band_data == -9999.0, np.nan, band_data)
            height, width = band_data.shape

            lon_coords = np.linspace(src.bounds.left, src.bounds.right, width)
            lat_coords = np.linspace(src.bounds.top, src.bounds.bottom, height)
            lon, lat = np.meshgrid(lon_coords, lat_coords)

            df = pd.DataFrame({
                "Latitude": lat.flatten(),
                "Longitude": lon.flatten(),
                "Value": band_data.flatten()
            })

            df.dropna(inplace=True)
            df_filtered = df[
                (df["Latitude"] >= lat_min) & (df["Latitude"] <= lat_max) &
                (df["Longitude"] >= lon_min) & (df["Longitude"] <= lon_max)
            ].copy()

            return df_filtered

    except Exception as e:
        st.error(f"❌ Terjadi kesalahan: {e}")
        return pd.DataFrame()

# --- Fungsi untuk Membuat Peta ---
def create_map(df, year, month, point_mode):
    if point_mode == 'Dinamis (berdasarkan curah hujan)':
        size_param = "Value"
        size_title = "Ukuran Titik (mm/bulan)"
        st.info("Peta ini menampilkan ukuran titik secara dinamis, di mana titik yang lebih besar menunjukkan curah hujan yang lebih tinggi.")
    else: # Konsisten
        size_param = None
        size_title = None
        st.info("Peta ini menampilkan ukuran titik yang konsisten untuk semua lokasi.")

    fig = px.scatter_mapbox(df,
                            lat="Latitude",
                            lon="Longitude",
                            color="Value",
                            size=size_param, # Mengatur parameter size
                            color_continuous_scale=px.colors.sequential.Viridis,
                            zoom=5,
                            mapbox_style="open-street-map",
                            title=f"Curah Hujan (mm/bulan) - {datetime(2000, int(month), 1).strftime('%B')} {year}",
                            hover_data={"Latitude": ':.2f', "Longitude": ':.2f', "Value": ':.2f'})
    
    # Menyesuaikan layout peta
    fig.update_layout(
        margin={"r":0,"t":40,"l":0,"b":0},
        coloraxis_colorbar=dict(title="Curah Hujan (mm)"),
    )

    # Mengatur ukuran titik yang konsisten
    if point_mode == 'Konsisten':
        fig.update_traces(marker=dict(size=8)) # Atur ukuran default jika mode konsisten

    st.plotly_chart(fig, use_container_width=True)


# --- Tombol Aksi ---
st.markdown("---")
col_buttons = st.columns(2)

if col_buttons[0].button('Proses Data & Tampilkan Peta 🗺️'):
    with st.spinner('Mengunduh dan memproses data... Ini mungkin memakan waktu beberapa saat.'):
        df_chirps = get_chirps_data(selected_year, selected_month_num, lat_min, lat_max, lon_min, lon_max)
    
    if not df_chirps.empty:
        create_map(df_chirps, selected_year, selected_month_num, point_size_mode)
    else:
        st.warning("Tidak ada data yang tersedia untuk ditampilkan. Harap periksa parameter yang Anda masukkan.")

if col_buttons[1].button('Download Data Excel ⬇️'):
    with st.spinner('Memproses data untuk diunduh...'):
        df_chirps_download = get_chirps_data(selected_year, selected_month_num, lat_min, lat_max, lon_min, lon_max)

    if not df_chirps_download.empty:
        excel_buffer = io.BytesIO()
        df_chirps_download.to_excel(excel_buffer, index=False, engine='xlsxwriter')
        excel_buffer.seek(0)

        st.download_button(
            label="Klik untuk Mengunduh File Excel",
            data=excel_buffer,
            file_name=f"CHIRPS_Data_{selected_year}_{selected_month_num}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.success("File Excel siap diunduh!")
    else:
        st.warning("Tidak ada data untuk diunduh. Harap proses data terlebih dahulu atau periksa parameter Anda.")

st.markdown("---")
st.info("Catatan: Data CHIRPS diunduh dari [CHG UCSB](https://data.chc.ucsb.edu/products/CHIRPS/).")