import streamlit as st
import requests
import rasterio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import os
import io

# --- Konfigurasi Aplikasi Streamlit ---
st.set_page_config(
    page_title="CHIRPS ERA5 Daily Data Downloader & Viewer",
    layout="wide",
    initial_sidebar_state="auto"
)

# --- Inisialisasi Session State ---
if 'chirps_data' not in st.session_state:
    st.session_state.chirps_data = {}

# --- Judul Aplikasi ---
st.title("🌧️ CHIRPS ERA5 Daily Data")
st.markdown("Aplikasi ini memungkinkan Anda mengunduh, memproses, dan memvisualisasikan data curah hujan harian CHIRPS v3.0 (ERA5). Hasil diunduh dalam format Excel agar mudah diolah.")
st.markdown("Dibuat Tsaqib")

# --- Input Pengguna di Sidebar ---
st.sidebar.header("Pilih Rentang Tanggal Harian")
col_start, col_end = st.sidebar.columns(2)

with col_start:
    start_date = st.date_input("Tanggal Awal:", value=datetime(2000, 1, 1), key='start_date')
with col_end:
    end_date = st.date_input("Tanggal Akhir:", value=datetime(2000, 1, 1), key='end_date')

point_size = st.sidebar.slider("Atur Ukuran Titik:", min_value=1, max_value=20, value=8, step=1)

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
def get_chirps_data_daily(date, lat_min, lat_max, lon_min, lon_max):
    """Mengunduh data CHIRPS harian (ERA5), memprosesnya, dan mengembalikan DataFrame."""
    year = date.year
    month = f"{date.month:02d}"
    day = f"{date.day:02d}"
    
    file_name = f"chirps-v3.0.{year}.{month}.{day}"
    # Perubahan URL untuk mengambil dari direktori ERA5
    url = f"https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/ERA5/{year}/{file_name}.tif"

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

            df_filtered['Date_Range'] = date.strftime('%Y-%m-%d')
            
            return df_filtered

    except Exception as e:
        st.error(f"❌ Gagal memproses data {date.strftime('%Y-%m-%d')}: {e}")
        return pd.DataFrame()

# --- Fungsi untuk Membuat Peta ---
def create_map(df, date_str, point_size):
    st.info("Peta ini menampilkan ukuran titik yang konsisten. Anda dapat mengatur ukurannya menggunakan slider di sidebar.")

    fig = px.scatter_mapbox(df,
                            lat="Latitude",
                            lon="Longitude",
                            color="Value",
                            color_continuous_scale=px.colors.sequential.Viridis,
                            zoom=5,
                            mapbox_style="open-street-map",
                            title=f"Curah Hujan (mm/hari) - {date_str}",
                            hover_data={"Latitude": ':.2f', "Longitude": ':.2f', "Value": ':.2f'})
    
    fig.update_layout(
        margin={"r":0,"t":40,"l":0,"b":0},
        coloraxis_colorbar=dict(title="Curah Hujan (mm)"),
    )

    fig.update_traces(marker=dict(size=point_size))

    st.plotly_chart(fig, use_container_width=True)

# --- Tombol Aksi ---
st.markdown("---")
col_buttons = st.columns(2)

if col_buttons[0].button('Proses Data & Tampilkan Peta 🗺️'):
    if start_date > end_date:
        st.error("Tanggal awal tidak boleh lebih besar dari tanggal akhir.")
    else:
        st.session_state.chirps_data = {}  # Reset data
        current_date = start_date
        
        with st.spinner(f'Mengunduh dan memproses data dari {start_date} s.d. {end_date}...'):
            while current_date <= end_date:
                df_chirps = get_chirps_data_daily(current_date, lat_min, lat_max, lon_min, lon_max)
                if not df_chirps.empty:
                    st.session_state.chirps_data[current_date.strftime('%Y-%m-%d')] = df_chirps
                
                current_date += timedelta(days=1)

        if st.session_state.chirps_data:
            st.success("✅ Semua data berhasil diproses!")
        else:
            st.warning("Tidak ada data yang tersedia untuk ditampilkan. Harap periksa parameter yang Anda masukkan.")

# --- Tampilkan Peta Jika Data Sudah Tersedia ---
if st.session_state.chirps_data:
    dates = sorted(st.session_state.chirps_data.keys())
    selected_date_index = st.slider("Pilih Tanggal untuk Peta:", 0, len(dates) - 1, 0, format=dates[0])
    selected_date = dates[selected_date_index]
    
    df_to_display = st.session_state.chirps_data[selected_date]
    create_map(df_to_display, selected_date, point_size)

if col_buttons[1].button('Download Semua Data Excel ⬇️'):
    if not st.session_state.chirps_data:
        st.error("Harap proses data terlebih dahulu sebelum mengunduh.")
    else:
        with st.spinner('Menggabungkan dan memproses data untuk diunduh...'):
            combined_df = pd.concat(list(st.session_state.chirps_data.values()), ignore_index=True)
            excel_buffer = io.BytesIO()
            combined_df.to_excel(excel_buffer, index=False, engine='xlsxwriter')
            excel_buffer.seek(0)
            
            start_date_str = sorted(st.session_state.chirps_data.keys())[0]
            end_date_str = sorted(st.session_state.chirps_data.keys())[-1]

            st.download_button(
                label="Klik untuk Mengunduh File Excel",
                data=excel_buffer,
                file_name=f"CHIRPS_Daily_ERA5_Data_{start_date_str}_to_{end_date_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.success("✅ File Excel siap diunduh!")

st.markdown("---")
st.info("Catatan: Data CHIRPS diunduh dari [CHG UCSB](https://data.chc.ucsb.edu/products/CHIRPS/).")