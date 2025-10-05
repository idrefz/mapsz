import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
import numpy as np
import requests
import json
from folium.plugins import MeasureControl, Fullscreen, MarkerCluster, HeatMap
import xml.etree.ElementTree as ET
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
    .metric-box {
        background-color: #ffffff;
        padding: 0.8rem;
        border-radius: 8px;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .feature-item {
        background-color: #f8f9fa;
        padding: 0.8rem;
        margin: 0.3rem 0;
        border-radius: 5px;
        border-left: 3px solid #28a745;
    }
    .stCheckbox > label {
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

def parse_kml_file(kml_file):
    """Parse file KML dan ekstrak fitur-fitur"""
    try:
        # Simpan file upload sementara
        with tempfile.NamedTemporaryFile(delete=False, suffix='.kml') as tmp_file:
            tmp_file.write(kml_file.getvalue())
            tmp_path = tmp_file.name
        
        # Baca KML dengan geopandas
        gdf = gpd.read_file(tmp_path, driver='KML')
        
        # Bersihkan file temporary
        os.unlink(tmp_path)
        
        return gdf
    except Exception as e:
        st.error(f"Error membaca file KML: {str(e)}")
        return None

def create_sample_kml_data():
    """Membuat data KML sampel jika tidak ada file upload"""
    # Data sampel beberapa kota di Indonesia
    sample_data = {
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
        'geometry': [
            Point(106.8272, -6.1754),
            Point(106.8229, -6.1963),
            Point(106.8952, -6.3024),
            Point(106.8133, -6.1352),
            Point(106.8380, -6.1256),
            Point(106.8025, -6.2194),
            Point(106.8203, -6.3139),
            Point(106.8400, -6.1250),
            Point(106.8950, -6.3010),
            Point(106.8223, -6.1761)
        ]
    }
    return gpd.GeoDataFrame(sample_data, crs='EPSG:4326')

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
        'default': 'gray'
    }
    return color_map.get(feature_type, color_map['default'])

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
        'default': 'info-sign'
    }
    return icon_map.get(feature_type, icon_map['default'])

def main():
    # Header
    st.markdown('<h1 class="main-header">🌍 Web GIS dengan KML Interaktif</h1>', unsafe_allow_html=True)
    
    # Sidebar - Upload dan Kontrol
    with st.sidebar:
        st.markdown('<h2 class="sidebar-header">📁 Upload File KML</h2>', unsafe_allow_html=True)
        
        # Upload file KML
        uploaded_file = st.file_uploader("Pilih file KML", type=['kml'], key="kml_uploader")
        
        if uploaded_file is not None:
            gdf = parse_kml_file(uploaded_file)
            if gdf is not None:
                st.success(f"✅ File KML berhasil dimuat! {len(gdf)} fitur ditemukan.")
        else:
            st.info("📝 Gunakan file KML Anda atau gunakan data sampel")
            if st.button("Gunakan Data Sampel"):
                gdf = create_sample_kml_data()
                st.success(f"✅ Data sampel dimuat! {len(gdf)} fitur ditemukan.")
            else:
                gdf = None
        
        if gdf is not None:
            st.markdown('<h2 class="sidebar-header">🎛️ Kontrol Tampilan</h2>', unsafe_allow_html=True)
            
            # Pilihan layer dasar
            basemap = st.selectbox(
                "Pilih Layer Peta:",
                ["OpenStreetMap", "Satellite", "Terrain", "Dark Mode", "Light Mode"]
            )
            
            # Kontrol tampilan fitur
            st.markdown("**Tampilan Fitur:**")
            show_markers = st.checkbox("Tampilkan Marker", value=True)
            show_popups = st.checkbox("Tampilkan Popup Info", value=True)
            show_heatmap = st.checkbox("Tampilkan Heatmap", value=False)
            use_clusters = st.checkbox("Gunakan Marker Clusters", value=False)
            
            # Filter berdasarkan jenis fitur
            st.markdown("**Filter berdasarkan Jenis:**")
            if 'Type' in gdf.columns:
                unique_types = gdf['Type'].unique().tolist()
                selected_types = st.multiselect(
                    "Pilih jenis yang ditampilkan:",
                    unique_types,
                    default=unique_types
                )
            else:
                st.info("Kolom 'Type' tidak ditemukan dalam data")
                selected_types = None
            
            # Filter berdasarkan nama
            st.markdown("**Filter berdasarkan Nama:**")
            if 'Name' in gdf.columns:
                search_term = st.text_input("Cari nama fitur:")
            else:
                search_term = ""
            
            # Style marker
            st.markdown("**Style Marker:**")
            marker_size = st.slider("Ukuran Marker:", 5, 20, 10)
            marker_opacity = st.slider("Opacity Marker:", 0.1, 1.0, 0.8)
    
    # Layout utama
    if gdf is not None:
        # Filter data berdasarkan pilihan
        filtered_gdf = gdf.copy()
        
        if selected_types and 'Type' in filtered_gdf.columns:
            filtered_gdf = filtered_gdf[filtered_gdf['Type'].isin(selected_types)]
        
        if search_term and 'Name' in filtered_gdf.columns:
            filtered_gdf = filtered_gdf[filtered_gdf['Name'].str.contains(search_term, case=False, na=False)]
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Buat peta
            m = create_base_map()
            
            # Konfigurasi tiles
            tile_layers = {
                "OpenStreetMap": "OpenStreetMap",
                "Satellite": "Esri.WorldImagery",
                "Terrain": "Stamen.Terrain",
                "Dark Mode": "CartoDB.DarkMatter",
                "Light Mode": "CartoDB.Positron"
            }
            
            # Tambahkan tile layer yang dipilih
            folium.TileLayer(tile_layers[basemap]).add_to(m)
            
            # Tambahkan marker clusters jika dipilih
            if use_clusters and show_markers:
                marker_cluster = MarkerCluster().add_to(m)
            
            # Tambahkan fitur ke peta
            for idx, row in filtered_gdf.iterrows():
                geometry = row.geometry
                
                # Handle different geometry types
                if geometry.geom_type == 'Point':
                    # Untuk titik, tambahkan marker
                    if show_markers:
                        # Dapatkan properti untuk popup
                        popup_content = ""
                        if show_popups:
                            popup_content = "<div style='min-width:200px'>"
                            for col in filtered_gdf.columns:
                                if col != 'geometry' and pd.notna(row[col]):
                                    popup_content += f"<b>{col}:</b> {row[col]}<br>"
                            popup_content += "</div>"
                        
                        # Tentukan warna dan ikon
                        feature_type = row.get('Type', 'default')
                        color = get_color_from_type(feature_type)
                        icon = get_icon_from_type(feature_type)
                        
                        # Buat marker
                        marker = folium.Marker(
                            location=[geometry.y, geometry.x],
                            popup=folium.Popup(popup_content, max_width=300) if show_popups else None,
                            tooltip=row.get('Name', 'Fitur'),
                            icon=folium.Icon(
                                color=color, 
                                icon=icon,
                                prefix='glyphicon'
                            )
                        )
                        
                        # Tambahkan ke cluster atau langsung ke peta
                        if use_clusters:
                            marker.add_to(marker_cluster)
                        else:
                            marker.add_to(m)
                
                elif geometry.geom_type in ['Polygon', 'MultiPolygon']:
                    # Untuk poligon, tambahkan shape
                    if geometry.geom_type == 'Polygon':
                        coords = [[[y, x] for x, y in geometry.exterior.coords]]
                    else:
                        coords = []
                        for poly in geometry.geoms:
                            coords.append([[y, x] for x, y in poly.exterior.coords])
                    
                    # Buat poligon
                    folium.Polygon(
                        locations=coords,
                        popup=row.get('Name', 'Poligon'),
                        color='blue',
                        fill=True,
                        fillColor='blue',
                        fillOpacity=0.2,
                        weight=2
                    ).add_to(m)
                
                elif geometry.geom_type in ['LineString', 'MultiLineString']:
                    # Untuk garis
                    if geometry.geom_type == 'LineString':
                        coords = [[y, x] for x, y in geometry.coords]
                    else:
                        coords = []
                        for line in geometry.geoms:
                            coords.extend([[y, x] for x, y in line.coords])
                    
                    folium.PolyLine(
                        locations=coords,
                        popup=row.get('Name', 'Garis'),
                        color='red',
                        weight=3
                    ).add_to(m)
            
            # Tambahkan heatmap jika dipilih
            if show_heatmap:
                heat_data = []
                for idx, row in filtered_gdf.iterrows():
                    if row.geometry.geom_type == 'Point':
                        heat_data.append([row.geometry.y, row.geometry.x, 1])
                
                if heat_data:
                    HeatMap(heat_data, radius=15, blur=10, gradient={0.4: 'blue', 0.65: 'lime', 1: 'red'}).add_to(m)
            
            # Tambahkan kontrol peta
            MeasureControl().add_to(m)
            Fullscreen().add_to(m)
            
            # Tampilkan peta
            st.markdown("### 🗺️ Peta Interaktif")
            map_data = st_folium(m, width=700, height=600, key="main_map")
            
            # Tampilkan informasi klik
            if map_data.get('last_clicked'):
                st.info(f"📍 Koordinat terklik: {map_data['last_clicked']}")
        
        with col2:
            st.markdown("### 📊 Informasi Data")
            
            # Metrics
            col_metric1, col_metric2 = st.columns(2)
            with col_metric1:
                st.metric("Total Fitur", len(filtered_gdf))
                st.metric("Fitur Ditampilkan", len(filtered_gdf))
            
            with col_metric2:
                if 'Type' in filtered_gdf.columns:
                    type_counts = filtered_gdf['Type'].value_counts()
                    most_common = type_counts.index[0] if len(type_counts) > 0 else "-"
                    st.metric("Jenis Terbanyak", most_common)
                
                geometry_types = filtered_gdf.geometry.geom_type.value_counts()
                main_geom = geometry_types.index[0] if len(geometry_types) > 0 else "-"
                st.metric("Tipe Geometri", main_geom)
            
            # Informasi kolom
            st.markdown("#### 📋 Kolom Data")
            columns_info = []
            for col in filtered_gdf.columns:
                if col != 'geometry':
                    non_null = filtered_gdf[col].notna().sum()
                    dtype = str(filtered_gdf[col].dtype)
                    columns_info.append({
                        'Kolom': col,
                        'Tipe': dtype,
                        'Non-Null': non_null,
                        'Contoh': str(filtered_gdf[col].iloc[0]) if non_null > 0 else '-'
                    })
            
            if columns_info:
                st.dataframe(pd.DataFrame(columns_info), use_container_width=True)
            
            # Daftar fitur
            st.markdown("#### 🎯 Daftar Fitur")
            if len(filtered_gdf) > 0:
                for idx, row in filtered_gdf.head(10).iterrows():  # Batasi 10 item pertama
                    with st.container():
                        feature_name = row.get('Name', f'Fitur {idx+1}')
                        feature_type = row.get('Type', 'Tidak diketahui')
                        
                        st.markdown(f"""
                        <div class="feature-item">
                            <b>{feature_name}</b><br>
                            <small>Type: {feature_type} | Geometry: {row.geometry.geom_type}</small>
                        </div>
                        """, unsafe_allow_html=True)
                
                if len(filtered_gdf) > 10:
                    st.info(f"Menampilkan 10 dari {len(filtered_gdf)} fitur. Gunakan filter untuk melihat lebih banyak.")
            else:
                st.warning("Tidak ada fitur yang sesuai dengan filter yang dipilih.")
            
            # Ekspor data
            st.markdown("#### 💾 Ekspor Data")
            col_exp1, col_exp2 = st.columns(2)
            
            with col_exp1:
                if st.button("Ekspor ke CSV"):
                    csv_data = filtered_gdf.drop('geometry', axis=1)
                    csv = csv_data.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name="filtered_gis_data.csv",
                        mime="text/csv"
                    )
            
            with col_exp2:
                if st.button("Ekspor ke GeoJSON"):
                    geojson = filtered_gdf.to_json()
                    st.download_button(
                        label="Download GeoJSON",
                        data=geojson,
                        file_name="filtered_gis_data.geojson",
                        mime="application/json"
                    )
    
    else:
        # Tampilan awal jika belum ada data
        st.info("""
        ## 📝 Instruksi Penggunaan
        
        1. **Upload file KML** Anda melalui sidebar di sebelah kiri
        2. Atau gunakan **data sampel** dengan mengklik tombol 'Gunakan Data Sampel'
        3. Setelah data dimuat, Anda dapat:
           - Memfilter fitur yang ditampilkan
           - Mengubah style peta
           - Mengontrol tampilan marker dan info
           - Melihat statistik data
        
        ### 🎯 Fitur yang Tersedia:
        - ✅ Upload dan parsing file KML
        - ✅ Filter data interaktif
        - ✅ Multiple base layers
        - ✅ Marker clusters dan heatmap
        - ✅ Informasi detail setiap fitur
        - ✅ Ekspor data hasil filter
        """)
        
        # Tampilkan peta kosong
        m = create_base_map()
        st_folium(m, width=800, height=500)

if __name__ == "__main__":
    main()
