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

# --- Streamlit Application Configuration ---
st.set_page_config(
    page_title="CHIRPS Daily Data Downloader & Viewer",
    layout="wide",
    initial_sidebar_state="auto"
)

# --- Initialize Session State ---
if 'chirps_data' not in st.session_state:
    st.session_state.chirps_data = {}
if 'data_processed' not in st.session_state:
    st.session_state.data_processed = False
if 'show_map' not in st.session_state:
    st.session_state.show_map = False

# --- Application Title ---
st.title("🌧️ CHIRPS Daily Data")
st.markdown("This application allows you to download, process, and visualize CHIRPS v3.0 daily rainfall data. The data is downloaded in Excel format for easy processing.")
st.markdown("Created by Tsaqib")

# --- User Input in Sidebar ---
st.sidebar.header("Select Daily Date Range")
col_start, col_end = st.sidebar.columns(2)

with col_start:
    start_date = st.date_input("Start Date:", value=datetime(2000, 1, 1), key='start_date')
with col_end:
    end_date = st.date_input("End Date:", value=datetime(2000, 1, 1), key='end_date')

point_size = st.sidebar.slider("Set Point Size:", min_value=1, max_value=20, value=8, step=1)

st.sidebar.markdown("---")
st.sidebar.header("Set Geographic Boundaries")

col1, col2 = st.sidebar.columns(2)
with col1:
    lat_min = st.number_input("Min Latitude:", value=-9.0, step=0.1, format="%.1f")
    lon_min = st.number_input("Min Longitude:", value=104.0, step=0.1, format="%.1f")
with col2:
    lat_max = st.number_input("Max Latitude:", value=-5.5, step=0.1, format="%.1f")
    lon_max = st.number_input("Max Longitude:", value=115.0, step=0.1, format="%.1f")

# --- Function to Download and Process Data ---
@st.cache_data(ttl=3600)
def get_chirps_data_daily(date, lat_min, lat_max, lon_min, lon_max):
    """Download daily CHIRPS data, process it, and return a DataFrame."""
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
        st.error(f"❌ Failed to process data for {date.strftime('%Y-%m-%d')}: {e}")
        return pd.DataFrame()

# --- Function to Create Map ---
def create_map(df, date_str, point_size):
    st.info("This map displays consistent point size. You can adjust the size using the slider in the sidebar.")

    fig = px.scatter_mapbox(df,
                            lat="Latitude",
                            lon="Longitude",
                            color="Value",
                            color_continuous_scale=px.colors.sequential.Viridis,
                            zoom=5,
                            mapbox_style="open-street-map",
                            title=f"Rainfall (mm/day) - {date_str}",
                            hover_data={"Latitude": ':.2f', "Longitude": ':.2f', "Value": ':.2f'})
    
    fig.update_layout(
        margin={"r":0,"t":40,"l":0,"b":0},
        coloraxis_colorbar=dict(title="Rainfall (mm)"),
    )

    fig.update_traces(marker=dict(size=point_size))

    st.plotly_chart(fig, use_container_width=True)

# --- Action Buttons ---
st.markdown("---")
if st.button('Process Data'):
    if start_date > end_date:
        st.error("The start date cannot be later than the end date.")
    else:
        st.session_state.chirps_data = {}
        st.session_state.data_processed = False
        st.session_state.show_map = False # Reset map status
        current_date = start_date
        
        with st.spinner(f'Downloading and processing data from {start_date} to {end_date}...'):
            while current_date <= end_date:
                df_chirps = get_chirps_data_daily(current_date, lat_min, lat_max, lon_min, lon_max)
                if not df_chirps.empty:
                    st.session_state.chirps_data[current_date.strftime('%Y-%m-%d')] = df_chirps
                
                current_date += timedelta(days=1)

        if st.session_state.chirps_data:
            st.session_state.data_processed = True
            st.success("✅ All data successfully processed!")
        else:
            st.warning("No data available to process. Please check the parameters you entered.")

# --- Display Map & Download Button (appears after data is processed) ---
if st.session_state.data_processed:
    st.markdown("---")
    st.subheader("Actions")
    col_actions = st.columns(2)
    
    # Show Map Button
    if col_actions[0].button('Show Map 🗺️'):
        st.session_state.show_map = True
    
    # Download ZIP Button
    if col_actions[1].button('Download All Data (ZIP) ⬇️'):
        with st.spinner('Creating ZIP archive...'):
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
                label="Click to Download ZIP File",
                data=zip_buffer,
                file_name=zip_file_name,
                mime="application/zip"
            )
            st.success("✅ ZIP file ready for download!")

    # Show Map if 'Show Map' button is clicked
    if st.session_state.show_map:
        st.markdown("---")
        st.subheader("Data Visualization")
        dates = sorted(st.session_state.chirps_data.keys())
        
        if dates:
            if len(dates) > 1:
                selected_date_index = st.slider("Select Date for Map:", 0, len(dates) - 1, 0)
                selected_date = dates[selected_date_index]
                st.write(f"Displaying data for date: **{selected_date}**")
            else:
                selected_date = dates[0]
                st.write(f"Displaying data for date: **{selected_date}**")
                
            df_to_display = st.session_state.chirps_data[selected_date]
            create_map(df_to_display, selected_date, point_size)
        else:
            st.warning("No data to visualize. Please process the data first.")

st.markdown("---")
st.info("Note: CHIRPS data downloaded from [CHG UCSB](https://data.chc.ucsb.edu/products/CHIRPS/).")
