import streamlit as st

st.set_page_config(
    page_title="CHIRPS Data Downloader",
    layout="wide"
)

st.title("CHIRPS Data Downloader Application")
st.markdown("""
This application allows you to download and visualize CHIRPS v3.0 rainfall data on both a daily and monthly scale. You can easily get the data as an Excel file, which makes it simple to use for your own analysis and reports.
Select your desired option from the navigation menu in the sidebar.
- **Monthly CHIRPS**: Download monthly rainfall data from year to year.
- **Daily CHIRPS**: Download daily rainfall data for a specific date range.
""")

st.markdown("Please select a page from the sidebar to begin.")

# --- Credits Section ---
st.markdown("---")
st.markdown("Created by:")
st.markdown("""
- **Ammar Abiyyu Tsaqib, S.Si.** *Department of Physics, Faculty of Mathematics and Natural Sciences, Yogyakarta States University* ammarabiyyu.2020@student.uny.ac.id
- **Yudhie Andriyana, M.Sc., Ph.D.** *Department of Statistics, Faculty of Mathematics and Natural Sciences, Universitas Padjadjaran* y.andriyana@unpad.ac.id
- **Dr. Annisa Nur Falah, M.Mat.** *Research Center for Computing, Research Organization for Electronics and Informatics, National Research and Innovation Agency (BRIN)* annisa.nur.falah.1@brin.go.id
""")

st.markdown("---")
st.info("Reference: CHIRPS documentation [CHG UCSB](https://www.chc.ucsb.edu/data/chirps3).")
st.info("Database: CHIRPS data downloaded from [Data CHG UCSB](https://data.chc.ucsb.edu/products/CHIRPS/).")
