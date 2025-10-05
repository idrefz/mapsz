import streamlit as st
import xml.etree.ElementTree as ET
import folium
from streamlit_folium import st_folium
import pandas as pd

st.set_page_config(page_title="Cek Data KML", layout="wide")

st.title("📍 Cek Data dari File KML")

uploaded_file = st.file_uploader("Upload file KML", type=["kml"])

if uploaded_file:
    # --- Parse file KML ---
    tree = ET.parse(uploaded_file)
    root = tree.getroot()

    # Namespace KML
    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    data = []
    for placemark in root.findall(".//kml:Placemark", ns):
        name = placemark.find("kml:name", ns)
        desc = placemark.find("kml:description", ns)
        name = name.text if name is not None else "Unnamed"
        desc = desc.text if desc is not None else ""

        # Cari Point
        point = placemark.find(".//kml:Point/kml:coordinates", ns)
        linestring = placemark.find(".//kml:LineString/kml:coordinates", ns)

        if point is not None:
            coord_str = point.text.strip()
            coords = [tuple(map(float, c.split(",")[:2])) for c in coord_str.split()]
            geom_type = "Point"
        elif linestring is not None:
            coord_str = linestring.text.strip()
            coords = [tuple(map(float, c.split(",")[:2])) for c in coord_str.split()]
            geom_type = "LineString"
        else:
            continue

        data.append({
            "Name": name,
            "Description": desc,
            "Type": geom_type,
            "Coordinates": coords
        })

    if not data:
        st.error("Tidak ada data Point atau LineString di file KML.")
    else:
        df = pd.DataFrame(data)
        st.success(f"Berhasil memuat {len(df)} data dari file KML.")
        st.dataframe(df[["Name", "Type", "Description"]])

        show_all = st.checkbox("Tampilkan semua titik/garis di peta", value=False)

        # --- Semua data ---
        if show_all:
            st.subheader("🗺️ Peta Semua Titik dan LineString")
            lat_center, lon_center = df["Coordinates"][0][0][1], df["Coordinates"][0][0][0]
            m = folium.Map(location=[lat_center, lon_center], zoom_start=8)

            for _, row in df.iterrows():
                coords = [(lat, lon) for lon, lat in row["Coordinates"]]
                if row["Type"] == "LineString":
                    folium.PolyLine(coords, color="blue", weight=3, tooltip=row["Name"]).add_to(m)
                else:
                    folium.Marker(coords[0], popup=row["Name"], tooltip=row["Name"]).add_to(m)

            st_folium(m, width=900, height=600)
        else:
            st.subheader("Pilih Data untuk Ditampilkan di Peta")
            selected_name = st.selectbox("Pilih Nama", df["Name"].unique())
            selected_data = df[df["Name"] == selected_name].iloc[0]
            coords = [(lat, lon) for lon, lat in selected_data["Coordinates"]]

            lat, lon = coords[0]
            m = folium.Map(location=[lat, lon], zoom_start=15)

            if selected_data["Type"] == "LineString":
                folium.PolyLine(coords, color="red", weight=4, tooltip=selected_data["Name"]).add_to(m)
                folium.Marker(coords[0], popup="Titik Awal").add_to(m)
                folium.Marker(coords[-1], popup="Titik Akhir").add_to(m)
            else:
                folium.Marker(coords[0], popup=selected_data["Name"]).add_to(m)

            folium.LatLngPopup().add_to(m)
            st.markdown("🖱️ Klik peta untuk menampilkan koordinat yang diklik.")
            output = st_folium(m, width=900, height=600)
            if output and output.get("last_clicked"):
                clicked = output["last_clicked"]
                st.info(f"Koordinat yang diklik: **Lat:** {clicked['lat']:.6f}, **Lon:** {clicked['lng']:.6f}")
else:
    st.info("Upload file `.kml` untuk mulai menampilkan data.")
