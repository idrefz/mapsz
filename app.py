import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Cek Data KML", layout="wide")

st.title("📍 Cek Data KML dari Excel")

# Upload file Excel
uploaded_file = st.file_uploader("Upload file Excel KML", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.success(f"File berhasil dibaca ({len(df)} baris)")
    st.dataframe(df)

    # Ambil koordinat pertama dari kolom Coordinates
    def extract_first_latlon(coord_str):
        try:
            # Pisahkan berdasarkan spasi atau koma
            if " " in coord_str:
                first_pair = coord_str.split(" ")[0]
            else:
                first_pair = coord_str.split(",0")[0]
            lon, lat = map(float, first_pair.split(",")[:2])
            return lat, lon
        except:
            return None, None

    df["Latitude"], df["Longitude"] = zip(*df["Coordinates"].apply(extract_first_latlon))
    df_valid = df.dropna(subset=["Latitude", "Longitude"])

    # Checkbox untuk tampilkan semua titik
    show_all = st.checkbox("Tampilkan semua titik di peta", value=False)

    if show_all:
        st.subheader("🗺️ Peta Semua Titik")
        # Ambil titik pertama sebagai pusat peta
        lat_center, lon_center = df_valid.iloc[0]["Latitude"], df_valid.iloc[0]["Longitude"]
        m = folium.Map(location=[lat_center, lon_center], zoom_start=8)

        for _, row in df_valid.iterrows():
            folium.Marker(
                [row["Latitude"], row["Longitude"]],
                popup=f"{row['Name']}<br>{row['Description']}",
                tooltip=row["Name"]
            ).add_to(m)

        st_folium(m, width=900, height=600)
    else:
        # Pilihan satu titik
        st.subheader("Pilih Data untuk Ditampilkan di Peta")
        selected_name = st.selectbox("Pilih Nama", df_valid["Name"].unique())

        selected_data = df_valid[df_valid["Name"] == selected_name].iloc[0]
        lat, lon = selected_data["Latitude"], selected_data["Longitude"]

        st.write(f"**Koordinat:** {lat}, {lon}")
        st.write(f"**Type:** {selected_data['Type']}")
        st.write(f"**Description:** {selected_data['Description']}")

        # --- Peta satu titik ---
        m = folium.Map(location=[lat, lon], zoom_start=17)
        folium.Marker([lat, lon], popup=f"{selected_name}").add_to(m)
        st_folium(m, width=900, height=600)

else:
    st.info("Upload file Excel untuk mulai menampilkan peta.")
