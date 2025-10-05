import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import numpy as np
import requests
import xml.etree.ElementTree as ET
from io import StringIO
import tempfile
import os

# Konfigurasi halaman
st.set_page_config(
    page_title="Web GIS dengan KML",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Style CSS kustom
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .sidebar-header {
        font-size: 1.3rem;
        color: #2e86ab;
        margin-bottom: 1rem;
    }
    .info-box {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .feature-item {
        background-color: #f8f9fa;
        padding: 0.8rem;
        margin: 0.3rem 0;
        border-radius: 5px;
        border-left: 3px solid #28a745;
    }
</style>
""", unsafe_allow_html=True)

def parse_kml_simple(kml_content):
    """Parse KML secara sederhana tanpa geopandas"""
    try:
        names = []
        descriptions = []
        types = []
        latitudes = []
        longitudes = []
        
        root = ET.fromstring(kml_content)
        
        # Namespace KML
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        # Cari semua Placemark
        for placemark in root.findall('.//kml:Placemark', ns):
            # Extract name
            name_elem = placemark.find('kml:name', ns)
            name = name_elem.text if name_elem is not None else "Unnamed"
            
            # Extract description
            desc_elem = placemark.find('kml:description', ns)
            description = desc_elem.text if desc_elem is not None else ""
            
            # Extract coordinates
            coords_elem = placemark.find('.//kml:coordinates', ns)
            if coords_elem is not None and coords_elem.text:
                # Ambil koordinat pertama (untuk point)
                coord_text = coords_elem.text.strip()
                first_coord = coord_text.split(',')[0:2]  # Ambil lng, lat
                if len(first_coord) == 2:
                    lng, lat = float(first_coord[0]), float(first_coord[1])
                    
                    names.append(name)
                    descriptions.append(description)
                    latitudes.append(lat)
                    longitudes.append(lng)
                    
                    # Coba tentukan type dari name/description
                    if 'monumen' in name.lower() or 'monas' in name.lower():
                        types.append('Monument')
                    elif 'taman' in name.lower() or 'park' in name.lower():
                        types.append('Park')
                    elif 'museum' in name.lower():
                        types.append('Museum')
                    elif 'sejarah' in name.lower() or 'historical' in name.lower():
                        types.append('Historical')
                    else:
                        types.append('Other')
        
        # Buat DataFrame
        if names:
            df = pd.DataFrame({
                'Name': names,
                'Description': descriptions,
                'Type': types,
                'latitude': latitudes,
                'longitude': longitudes
            })
            return df
        else:
            st.warning("Tidak ada data koordinat yang ditemukan dalam file KML")
            return None
            
    except Exception as e:
        st.error(f"Error parsing KML: {str(e)}")
        return None

def create_sample_data():
    """Membuat data sampel"""
    data = {
        'Name': [
            'Monumen Nasional', 'Bundaran HI', 'Taman Mini', 
            'Kota Tua Jakarta', 'Ancol Dreamland', 'GBK Senayan',
            'Ragunan Zoo', 'Dufan', 'TMII', 'Museum Nasional'
        ],
        'Description': [
            'Monumen kebanggaan Jakarta', 'Bundaran Hotel Indonesia',
            'Taman Mini Indonesia Indah', 'Kawasan sejarah Jakarta',
            'Taman rekreasi Ancol', 'Gelora Bung Karno',
            'Kebun binatang Ragunan', 'Dunia Fantasi',
            'Taman Mini Indonesia Indah', 'Museum Nasional Indonesia'
        ],
        'Type': ['Monument', 'Landmark', 'Park', 'Historical', 'Entertainment',
                'Sports', 'Zoo', 'Entertainment', 'Park', 'Museum'],
        'latitude': [-6.1754, -6.1963, -6.3024, -6.1352, -6.1256,
                    -6.2194, -6.3139, -6.1250, -6.3010, -6.1761],
        'longitude': [106.8272, 106.8229, 106.8952, 106.8133, 106.8380,
                     106.8025, 106.8203, 106.8400, 106.8950, 106.8223]
    }
    return pd.DataFrame(data)

def create_base_map(location=[-6.2088, 106.8456], zoom_start=10):
    """Membuat peta dasar"""
    return folium.Map(
        location=location,
        zoom_start=zoom_start,
        tiles='OpenStreetMap',
        control_scale=True
    )

def get_color_from_type(feature_type):
    """Mengembalikan warna berdasarkan jenis fitur"""
    color_map = {
        'Monument': 'red',
        'Landmark': 'darkred',
        'Park': 'green',
        'Historical': 'orange',
        'Entertainment': 'purple',
        'Sports': 'blue',
        'Zoo': 'darkgreen',
        'Museum': 'cadetblue',
        'Other': 'gray'
    }
    return color_map.get(feature_type, 'gray')

def get_icon_from_type(feature_type):
    """Mengembalikan ikon berdasarkan jenis fitur"""
    icon_map = {
        'Monument': 'info-sign',
        'Landmark': 'flag',
        'Park': 'tree-conifer',
        'Historical': 'bookmark',
        'Entertainment': 'facetime-video',
        'Sports': 'play-circle',
        'Zoo': 'heart',
        'Museum': 'education',
        'Other': 'info-sign'
    }
    return icon_map.get(feature_type, 'info-sign')

def main():
    # Header
    st.markdown('<h1 class="main-header">🌍 Web GIS dengan KML Interaktif</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown('<h2 class="sidebar-header">📁 Upload File KML</h2>', unsafe_allow_html=True)
        
        # Upload file KML
        uploaded_file = st.file_uploader("Pilih file KML", type=['kml'], key="kml_uploader")
        
        df = None
        
        if uploaded_file is not None:
            # Baca konten file
            kml_content = uploaded_file.read().decode('utf-8')
            df = parse_kml_simple(kml_content)
            if df is not None:
                st.success(f"✅ File KML berhasil dimuat! {len(df)} fitur ditemukan.")
        else:
            # Coba baca file zxcmcnc.kml jika ada
            try:
                if os.path.exists('zxcmcnc.kml'):
                    with open('zxcmcnc.kml', 'r', encoding='utf-8') as f:
                        kml_content = f.read()
                    df = parse_kml_simple(kml_content)
                    if df is not None:
                        st.success(f"✅ File zxcmcnc.kml berhasil dimuat! {len(df)} fitur ditemukan.")
                else:
                    st.info("📝 Upload file KML atau gunakan data sampel")
            except Exception as e:
                st.warning(f"Tidak bisa membaca zxcmcnc.kml: {str(e)}")
        
        # Tombol data sampel
        if df is None:
            if st.button("Gunakan Data Sampel"):
                df = create_sample_data()
                st.success(f"✅ Data sampel dimuat! {len(df)} fitur ditemukan.")
        
        if df is not None:
            st.markdown('<h2 class="sidebar-header">🎛️ Kontrol Tampilan</h2>', unsafe_allow_html=True)
            
            # Pilihan layer dasar
            basemap = st.selectbox(
                "Pilih Layer Peta:",
                ["OpenStreetMap", "Satellite", "Terrain", "Dark Mode"]
            )
            
            # Kontrol tampilan
            st.markdown("**Tampilan Fitur:**")
            show_markers = st.checkbox("Tampilkan Marker", value=True)
            show_popups = st.checkbox("Tampilkan Popup Info", value=True)
            show_heatmap = st.checkbox("Tampilkan Heatmap", value=False)
            use_clusters = st.checkbox("Gunakan Marker Clusters", value=False)
            
            # Filter berdasarkan jenis
            st.markdown("**Filter berdasarkan Jenis:**")
            unique_types = df['Type'].unique().tolist()
            selected_types = st.multiselect(
                "Pilih jenis yang ditampilkan:",
                unique_types,
                default=unique_types
            )
            
            # Filter berdasarkan nama
            st.markdown("**Filter berdasarkan Nama:**")
            search_term = st.text_input("Cari nama fitur:")
    
    # Layout utama
    if df is not None:
        # Filter data
        filtered_df = df[df['Type'].isin(selected_types)] if selected_types else df
        
        if search_term:
            filtered_df = filtered_df[filtered_df['Name'].str.contains(search_term, case=False, na=False)]
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Buat peta
            m = create_base_map()
            
            # Konfigurasi tiles
            tile_layers = {
                "OpenStreetMap": "OpenStreetMap",
                "Satellite": "Esri.WorldImagery",
                "Terrain": "Stamen.Terrain",
                "Dark Mode": "CartoDB.DarkMatter"
            }
            
            folium.TileLayer(tile_layers[basemap]).add_to(m)
            
            # Tambahkan marker clusters jika dipilih
            if use_clusters and show_markers:
                from folium.plugins import MarkerCluster
                marker_cluster = MarkerCluster().add_to(m)
            
            # Tambahkan marker ke peta
            if show_markers:
                for idx, row in filtered_df.iterrows():
                    # Konten popup
                    popup_content = ""
                    if show_popups:
                        popup_content = f"""
                        <div style='min-width:200px'>
                            <b>{row['Name']}</b><br>
                            <b>Type:</b> {row['Type']}<br>
                            <b>Description:</b> {row['Description']}<br>
                            <b>Koordinat:</b> {row['latitude']:.4f}, {row['longitude']:.4f}
                        </div>
                        """
                    
                    # Style marker
                    color = get_color_from_type(row['Type'])
                    icon = get_icon_from_type(row['Type'])
                    
                    marker = folium.Marker(
                        location=[row['latitude'], row['longitude']],
                        popup=folium.Popup(popup_content, max_width=300) if show_popups else None,
                        tooltip=row['Name'],
                        icon=folium.Icon(color=color, icon=icon, prefix='glyphicon')
                    )
                    
                    # Tambahkan ke cluster atau langsung ke peta
                    if use_clusters:
                        marker.add_to(marker_cluster)
                    else:
                        marker.add_to(m)
            
            # Tambahkan heatmap
            if show_heatmap:
                from folium.plugins import HeatMap
                heat_data = [[row['latitude'], row['longitude'], 1] for idx, row in filtered_df.iterrows()]
                HeatMap(heat_data, radius=15, blur=10).add_to(m)
            
            # Tambahkan kontrol
            from folium.plugins import MeasureControl, Fullscreen
            MeasureControl().add_to(m)
            Fullscreen().add_to(m)
            
            # Tampilkan peta
            st.markdown("### 🗺️ Peta Interaktif")
            map_data = st_folium(m, width=700, height=600, key="main_map")
            
            # Info klik
            if map_data.get('last_clicked'):
                st.info(f"📍 Koordinat terklik: {map_data['last_clicked']}")
        
        with col2:
            st.markdown("### 📊 Informasi Data")
            
            # Metrics
            col_metric1, col_metric2 = st.columns(2)
            with col_metric1:
                st.metric("Total Fitur", len(df))
                st.metric("Ditampilkan", len(filtered_df))
            
            with col_metric2:
                type_counts = filtered_df['Type'].value_counts()
                most_common = type_counts.index[0] if len(type_counts) > 0 else "-"
                st.metric("Jenis Terbanyak", most_common)
                
                total_locations = len(filtered_df)
                st.metric("Lokasi Unik", total_locations)
            
            # Chart distribusi
            st.markdown("#### 📈 Distribusi Jenis")
            type_counts = filtered_df['Type'].value_counts()
            if not type_counts.empty:
                st.bar_chart(type_counts)
            
            # Daftar fitur
            st.markdown("#### 🎯 Daftar Fitur")
            for idx, row in filtered_df.head(8).iterrows():
                st.markdown(f"""
                <div class="feature-item">
                    <b>{row['Name']}</b><br>
                    <small>Type: {row['Type']} | {row['latitude']:.4f}, {row['longitude']:.4f}</small>
                </div>
                """, unsafe_allow_html=True)
            
            if len(filtered_df) > 8:
                st.info(f"Menampilkan 8 dari {len(filtered_df)} fitur")
            
            # Ekspor data
            st.markdown("#### 💾 Ekspor Data")
            if st.button("Ekspor ke CSV"):
                csv = filtered_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="gis_data.csv",
                    mime="text/csv"
                )
    
    else:
        # Tampilan awal
        st.info("""
        ## 📝 Instruksi Penggunaan
        
        1. **Upload file KML** Anda melalui sidebar
        2. Atau letakkan file `zxcmcnc.kml` di folder yang sama
        3. Atau gunakan **data sampel**
        
        Aplikasi akan otomatis membaca dan menampilkan data KML Anda!
        """)
        
        # Peta kosong
        m = create_base_map()
        st_folium(m, width=800, height=500)

if __name__ == "__main__":
    main()
