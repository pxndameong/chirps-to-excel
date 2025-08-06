import streamlit as st
import requests
import rasterio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import os
import io
import zipfile

# --- Konfigurasi Aplikasi Streamlit ---
st.set_page_config(
    page_title="CHIRPS Daily Data Downloader & Viewer",
    layout="wide",
    initial_sidebar_state="auto"
)

# --- Inisialisasi Session State ---
if 'chirps_data' not in st.session_state:
    st.session_state.chirps_data = {}
if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
if 'show_map' not in st.session_state:
    st.session_state.show_map = False

# --- Judul Aplikasi ---
st.title("🌧️ CHIRPS Daily Data")
st.markdown("Aplikasi ini memungkinkan Anda mengunduh, memproses, dan memvisualisasikan data curah hujan harian CHIRPS v3.0. Hasil diunduh dalam format Excel agar mudah diolah.")
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
    """Mengunduh data CHIRPS harian, memprosesnya, dan mengembalikan DataFrame."""
    year = date.year
    month = f"{date.month:02d}"
    day = f"{date.day:02d}"
    
    file_name = f"chirps-v3.0.{year}.{month}.{day}"
    url = f"https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/IMERGlate-v07/{year}/{file_name}.tif"

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
if st.button('Proses Data'):
    if start_date > end_date:
        st.error("Tanggal awal tidak boleh lebih besar dari tanggal akhir.")
    else:
        st.session_state.chirps_data = {}
        st.session_state.data_processed = False
        st.session_state.show_map = False # Reset status peta
        current_date = start_date
        
        with st.spinner(f'Mengunduh dan memproses data dari {start_date} s.d. {end_date}...'):
            while current_date <= end_date:
                df_chirps = get_chirps_data_daily(current_date, lat_min, lat_max, lon_min, lon_max)
                if not df_chirps.empty:
                    st.session_state.chirps_data[current_date.strftime('%Y-%m-%d')] = df_chirps
                
                current_date += timedelta(days=1)

        if st.session_state.chirps_data:
            st.session_state.data_processed = True
            st.success("✅ Semua data berhasil diproses!")
        else:
            st.warning("Tidak ada data yang tersedia untuk diproses. Harap periksa parameter yang Anda masukkan.")

# --- Tampilkan Peta & Tombol Unduh (muncul setelah proses data) ---
if st.session_state.data_processed:
    st.markdown("---")
    st.subheader("Aksi")
    col_actions = st.columns(2)
    
    # Tombol Tampilkan Peta
    if col_actions[0].button('Tampilkan Peta 🗺️'):
        st.session_state.show_map = True
    
    # Tombol Unduh ZIP
    if col_actions[1].button('Download Semua Data (ZIP) ⬇️'):
        with st.spinner('Membuat file arsip ZIP...'):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for date_key, df_data in st.session_state.chirps_data.items():
                    excel_buffer = io.BytesIO()
                    df_data.to_excel(excel_buffer, index=False, engine='xlsxwriter')
                    excel_buffer.seek(0)
                    zip_file.writestr(f"CHIRPS_Data_{date_key}.xlsx", excel_buffer.getvalue())
            
            zip_buffer.seek(0)
            
            start_date_str = sorted(st.session_state.chirps_data.keys())[0]
            end_date_str = sorted(st.session_state.chirps_data.keys())[-1]
            zip_file_name = f"CHIRPS_Daily_Data_{start_date_str}_to_{end_date_str}.zip"
            
            st.download_button(
                label="Klik untuk Mengunduh File ZIP",
                data=zip_buffer,
                file_name=zip_file_name,
                mime="application/zip"
            )
            st.success("✅ File ZIP siap diunduh!")

    # Menampilkan Peta jika tombol 'Tampilkan Peta' ditekan
    if st.session_state.show_map:
        st.markdown("---")
        st.subheader("Visualisasi Data")
        dates = sorted(st.session_state.chirps_data.keys())
        
        if dates:
            if len(dates) > 1:
                selected_date_index = st.slider("Pilih Tanggal untuk Peta:", 0, len(dates) - 1, 0)
                selected_date = dates[selected_date_index]
                st.write(f"Menampilkan data untuk tanggal: **{selected_date}**")
            else:
                selected_date = dates[0]
                st.write(f"Menampilkan data untuk tanggal: **{selected_date}**")
                
            df_to_display = st.session_state.chirps_data[selected_date]
            create_map(df_to_display, selected_date, point_size)
        else:
            st.warning("Tidak ada data untuk divisualisasikan. Silakan proses data terlebih dahulu.")

st.markdown("---")
st.info("Catatan: Data CHIRPS diunduh dari [CHG UCSB](https://data.chc.ucsb.edu/products/CHIRPS/).")