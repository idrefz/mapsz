import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString, Polygon, MultiLineString, MultiPolygon
import tempfile
import os
from datetime import datetime
import math
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import fiona
from fiona.drvsupport import supported_drivers

# Enable KML support in fiona
supported_drivers['KML'] = 'rw'
supported_drivers['libkml'] = 'rw'

# Konfigurasi halaman
st.set_page_config(
    page_title="GIS KML Folder Selector",
    page_icon="📁",
    layout="wide"
)

# Konfigurasi path KML master
KML_MASTER_PATH = "zxcmcnc.kml"

# Initialize session state
if 'gdf_master' not in st.session_state:
    st.session_state.gdf_master = None
if 'gdf_filtered' not in st.session_state:
    st.session_state.gdf_filtered = None
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'gdf_nearby' not in st.session_state:
    st.session_state.gdf_nearby = None
if 'gangguan_coords' not in st.session_state:
    st.session_state.gangguan_coords = None
if 'map_click_data' not in st.session_state:
    st.session_state.map_click_data = None
if 'last_click_coords' not in st.session_state:
    st.session_state.last_click_coords = None
if 'available_folders' not in st.session_state:
    st.session_state.available_folders = []
if 'selected_folders' not in st.session_state:
    st.session_state.selected_folders = []
if 'folder_features' not in st.session_state:
    st.session_state.folder_features = {}

# Fungsi untuk extract folders dari KML
def extract_folders_from_kml(file_path):
    """Extract semua folder dari file KML"""
    folders = {}
    
    try:
        # Method 1: Parsing manual XML
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Namespace untuk KML
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        # Find all Folders
        for folder in root.findall('.//kml:Folder', ns):
            folder_name_elem = folder.find('kml:name', ns)
            if folder_name_elem is not None:
                folder_name = folder_name_elem.text
                folders[folder_name] = []
                
                # Extract features dalam folder ini
                for placemark in folder.findall('.//kml:Placemark', ns):
                    name_elem = placemark.find('kml:name', ns)
                    feature_name = name_elem.text if name_elem is not None else "Unnamed"
                    folders[folder_name].append(feature_name)
        
        # Jika tidak ada folder, coba grouping by other attributes
        if not folders:
            # Coba grouping by description atau other fields
            gdf = gpd.read_file(file_path, driver='KML')
            if not gdf.empty:
                # Cari kolom yang mungkin mengandung folder information
                folder_columns = []
                for col in gdf.columns:
                    if any(keyword in col.lower() for keyword in ['folder', 'group', 'category', 'type', 'layer']):
                        folder_columns.append(col)
                
                if folder_columns:
                    for col in folder_columns:
                        unique_values = gdf[col].dropna().unique()
                        for value in unique_values:
                            if value and value != '':
                                folders[f"{col}: {value}"] = list(gdf[gdf[col] == value]['name'].dropna().values if 'name' in gdf.columns else [f"Feature {i}" for i in range(len(gdf[gdf[col] == value]))])
                
                # Jika masih tidak ada, buat folder berdasarkan geometry type
                if not folders:
                    geom_types = gdf.geometry.type.unique()
                    for geom_type in geom_types:
                        features = list(gdf[gdf.geometry.type == geom_type]['name'].dropna().values if 'name' in gdf.columns else [f"{geom_type} {i}" for i in range(len(gdf[gdf.geometry.type == geom_type]))])
                        folders[f"Geometry: {geom_type}"] = features
        
        return folders
        
    except Exception as e:
        st.warning(f"Folder extraction warning: {e}")
        return {}

# Fungsi untuk memfilter features berdasarkan folder yang dipilih
def filter_features_by_folders(gdf, selected_folders, folder_features):
    """Filter features berdasarkan folder yang dipilih"""
    if not selected_folders:
        return gdf
    
    try:
        # Untuk simplicity, kita akan filter berdasarkan nama features
        # Dalam implementasi real, Anda mungkin perlu mapping yang lebih complex
        selected_features = []
        
        for folder in selected_folders:
            if folder in folder_features:
                selected_features.extend(folder_features[folder])
        
        # Filter dataframe berdasarkan nama features
        if 'name' in gdf.columns:
            filtered_gdf = gdf[gdf['name'].isin(selected_features)]
        else:
            # Jika tidak ada kolom name, kita tidak bisa filter dengan tepat
            st.warning("Tidak ada kolom 'name' untuk filtering folder")
            return gdf
        
        return filtered_gdf
        
    except Exception as e:
        st.error(f"Error filtering by folders: {e}")
        return gdf

# Fungsi untuk membaca KML dengan folder support
def load_kml_with_folders(file_path):
    """Membaca KML dengan support folder structure"""
    try:
        # Load data dengan geopandas
        gdf = gpd.read_file(file_path, driver='KML')
        
        if gdf.empty:
            st.error("❌ KML file kosong atau tidak terbaca")
            return None, {}
        
        # Extract folder structure
        folders = extract_folders_from_kml(file_path)
        
        # Jika tidak ada folders terdeteksi, buat default folder
        if not folders:
            folders = {"All Features": list(gdf['name'].dropna().values) if 'name' in gdf.columns else [f"Feature {i}" for i in range(len(gdf))]}
        
        return gdf, folders
        
    except Exception as e:
        st.error(f"❌ Error loading KML with folders: {e}")
        return None, {}

def clean_geometry(gdf):
    """Membersihkan geometry"""
    try:
        gdf = gdf[gdf.geometry.notna()]
        gdf = gdf[~gdf.geometry.is_empty]
        return gdf
    except Exception as e:
        st.warning(f"Geometry cleaning warning: {e}")
        return gdf

def filter_features_nearby(gdf, center_point, radius_km=5):
    """Filter features dalam radius tertentu"""
    try:
        if gdf is None or gdf.empty:
            return gpd.GeoDataFrame()
        
        buffer_degrees = radius_km / 111
        buffer_zone = center_point.buffer(buffer_degrees)
        
        # Gunakan spatial index untuk percepat query
        spatial_index = gdf.sindex
        possible_matches_index = list(spatial_index.intersection(buffer_zone.bounds))
        possible_matches = gdf.iloc[possible_matches_index]
        
        # Filter yang benar-benar intersect
        nearby_features = possible_matches[possible_matches.intersects(buffer_zone)].copy()
        
        if nearby_features.empty:
            return nearby_features
        
        # Hitung jarak
        def calculate_distance(geom):
            try:
                return center_point.distance(geom) * 111000
            except:
                return float('inf')
        
        nearby_features['jarak_meter'] = nearby_features.geometry.apply(calculate_distance)
        nearby_features = nearby_features.sort_values('jarak_meter')
        
        return nearby_features
        
    except Exception as e:
        st.error(f"Error filtering: {e}")
        return gpd.GeoDataFrame()

def create_detailed_popup(row):
    """Membuat popup detail"""
    try:
        popup_html = "<div style='max-width: 350px; max-height: 400px; overflow-y: auto;'>"
        popup_html += "<h4 style='margin-bottom: 10px; color: #1f77b4;'>📋 Detail Feature</h4>"
        
        for col in row.index:
            if col != 'geometry' and pd.notna(row[col]) and row[col] not in ['', None]:
                value = str(row[col])
                if len(value) > 150:
                    value = value[:150] + "..."
                
                popup_html += f"""
                <div style='margin-bottom: 8px; border-bottom: 1px solid #eee; padding-bottom: 5px;'>
                    <strong style='color: #333;'>{col}:</strong><br>
                    <span style='color: #666; word-wrap: break-word;'>{value}</span>
                </div>
                """
        
        geometry_type = row.geometry.geom_type if hasattr(row, 'geometry') else 'Unknown'
        jarak = row.get('jarak_meter', 'N/A')
        
        popup_html += f"""
        <div style='margin-top: 10px; padding-top: 10px; border-top: 2px solid #007cba; background: #f0f8ff; padding: 10px; border-radius: 5px;'>
            <strong>Jarak:</strong> {jarak:.0f} meter<br>
            <strong>Tipe Geometry:</strong> {geometry_type}
        </div>
        </div>
        """
        return popup_html
    except Exception as e:
        return f"<div>Popup error: {str(e)}</div>"

def create_interactive_map(gdf_nearby, gangguan_coords, zoom=15):
    """Membuat peta interaktif"""
    try:
        if gangguan_coords:
            center_loc = gangguan_coords
        else:
            center_loc = [-6.2, 106.8]
        
        m = folium.Map(location=center_loc, zoom_start=zoom, control_scale=True)
        m.add_child(folium.LatLngPopup())
        
        # Instruksi klik
        folium.Marker(
            location=center_loc,
            icon=folium.DivIcon(
                html='<div style="background-color: white; padding: 10px; border: 3px solid #007cba; border-radius: 8px; font-size: 14px; font-weight: bold; color: #007cba;">📍 KLIK DI PETA UNTUK PILIH LOKASI GANGGUAN</div>'
            )
        ).add_to(m)
        
        # Marker gangguan
        if gangguan_coords:
            folium.Marker(
                location=gangguan_coords,
                popup=f"<b>🚨 TITIK GANGGUAN</b><br>Lat: {gangguan_coords[0]:.6f}<br>Lon: {gangguan_coords[1]:.6f}",
                icon=folium.Icon(color='red', icon='exclamation-triangle', prefix='fa')
            ).add_to(m)
            
            folium.Circle(
                location=gangguan_coords,
                radius=radius_km * 1000,
                color='red',
                fill=True,
                fillColor='red',
                fillOpacity=0.1,
                popup=f"Area Pencarian ({radius_km}km)"
            ).add_to(m)
        
        # Tambahkan features
        if gdf_nearby is not None and not gdf_nearby.empty:
            for idx, row in gdf_nearby.iterrows():
                try:
                    if row.geometry.geom_type == 'Point':
                        folium.Marker(
                            location=[row.geometry.y, row.geometry.x],
                            popup=folium.Popup(create_detailed_popup(row), max_width=400),
                            icon=folium.Icon(color='blue', icon='info-sign')
                        ).add_to(m)
                    
                    elif row.geometry.geom_type in ['LineString', 'MultiLineString']:
                        folium.GeoJson(
                            row.geometry.__geo_interface__,
                            style_function=lambda x: {'color': 'green', 'weight': 4, 'opacity': 0.8},
                            popup=folium.Popup(create_detailed_popup(row), max_width=400)
                        ).add_to(m)
                    
                    elif row.geometry.geom_type in ['Polygon', 'MultiPolygon']:
                        folium.GeoJson(
                            row.geometry.__geo_interface__,
                            style_function=lambda x: {'fillColor': 'orange', 'color': 'orange', 'weight': 2, 'fillOpacity': 0.3},
                            popup=folium.Popup(create_detailed_popup(row), max_width=400)
                        ).add_to(m)
                        
                except Exception as e:
                    continue
        
        return m
        
    except Exception as e:
        st.error(f"Map creation error: {e}")
        return folium.Map(location=[-6.2, 106.8], zoom_start=10)

def analyze_from_map_click(click_data, radius_km):
    """Analisis dari klik peta"""
    try:
        if click_data and 'lat' in click_data and 'lng' in click_data:
            lat = click_data['lat']
            lng = click_data['lng']
            
            st.session_state.gangguan_coords = [lat, lng]
            st.session_state.analysis_done = True
            
            gangguan_point = Point(lng, lat)
            
            with st.spinner(f"Mencari features dalam radius {radius_km} km..."):
                # Gunakan filtered data jika ada
                data_to_use = st.session_state.gdf_filtered if st.session_state.gdf_filtered is not None else st.session_state.gdf_master
                st.session_state.gdf_nearby = filter_features_nearby(
                    data_to_use, 
                    gangguan_point, 
                    radius_km
                )
            
            return True
        return False
    except Exception as e:
        st.error(f"Analysis error: {e}")
        return False

# UI Streamlit
st.title("📁 GIS KML Folder Selector")
st.markdown("**Pilih folder tertentu dari KML → Analisis per area gangguan**")

# Sidebar
with st.sidebar:
    st.header("📁 Folder Selection")
    st.markdown("---")
    
    # Load KML data
    if st.button("🔄 Load KML Data", use_container_width=True):
        with st.spinner("Loading KML data..."):
            st.session_state.gdf_master, st.session_state.folder_features = load_kml_with_folders(KML_MASTER_PATH)
            if st.session_state.gdf_master is not None:
                st.session_state.available_folders = list(st.session_state.folder_features.keys())
                st.session_state.gdf_filtered = st.session_state.gdf_master
                st.success(f"✅ Loaded {len(st.session_state.gdf_master)} features")
    
    st.markdown("---")
    
    # Folder selection
    if st.session_state.available_folders:
        st.subheader("📂 Pilih Folder")
        
        # Select all checkbox
        if st.checkbox("Pilih Semua Folder", value=True):
            st.session_state.selected_folders = st.session_state.available_folders.copy()
        else:
            st.session_state.selected_folders = []
        
        # Individual folder selection
        for folder in st.session_state.available_folders:
            feature_count = len(st.session_state.folder_features[folder])
            if st.checkbox(f"{folder} ({feature_count} features)", 
                          value=folder in st.session_state.selected_folders,
                          key=f"folder_{folder}"):
                if folder not in st.session_state.selected_folders:
                    st.session_state.selected_folders.append(folder)
            else:
                if folder in st.session_state.selected_folders:
                    st.session_state.selected_folders.remove(folder)
        
        # Apply folder filter
        if st.button("✅ Terapkan Filter Folder", type="primary", use_container_width=True):
            if st.session_state.selected_folders:
                with st.spinner("Memfilter features..."):
                    st.session_state.gdf_filtered = filter_features_by_folders(
                        st.session_state.gdf_master,
                        st.session_state.selected_folders,
                        st.session_state.folder_features
                    )
                st.success(f"✅ Filtered: {len(st.session_state.gdf_filtered)} features")
            else:
                st.session_state.gdf_filtered = st.session_state.gdf_master
                st.info("ℹ️ Menampilkan semua features")
    
    st.markdown("---")
    st.header("📍 Input Lokasi Gangguan")
    
    st.subheader("🎯 Klik di Peta")
    st.info("Klik langsung di peta untuk memilih lokasi gangguan")
    
    st.subheader("📝 Input Manual")
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("Latitude", value=-6.200000, format="%.6f", step=0.000001, key="lat_input")
    with col2:
        lon = st.number_input("Longitude", value=106.816666, format="%.6f", step=0.000001, key="lon_input")
    
    radius_km = st.slider("Radius Pencarian (km)", 1, 50, 10, key="radius_input")
    
    col1, col2 = st.columns(2)
    with col1:
        analyze_btn = st.button("🚀 Analisis Gangguan", type="primary", use_container_width=True)
    with col2:
        if st.button("🔄 Reset All", use_container_width=True):
            for key in ['analysis_done', 'gdf_nearby', 'gangguan_coords', 'map_click_data', 'last_click_coords', 'selected_folders', 'gdf_filtered']:
                if key in st.session_state:
                    st.session_state[key] = None
            st.session_state.selected_folders = st.session_state.available_folders.copy() if st.session_state.available_folders else []
            st.rerun()
    
    st.markdown("---")
    zoom_level = st.slider("Zoom Level Peta", 10, 18, 15, key="zoom_input")

# Main content
if st.session_state.gdf_master is not None:
    # Show current filter status
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_features = len(st.session_state.gdf_master)
        st.metric("Total Features", total_features)
    
    with col2:
        if st.session_state.gdf_filtered is not None:
            filtered_count = len(st.session_state.gdf_filtered)
            st.metric("Features Terfilter", filtered_count)
        else:
            st.metric("Features Terfilter", total_features)
    
    with col3:
        selected_count = len(st.session_state.selected_folders) if st.session_state.selected_folders else len(st.session_state.available_folders)
        st.metric("Folder Terpilih", f"{selected_count}/{len(st.session_state.available_folders)}")
    
    # Peta interaktif
    st.header("🗺️ Peta Interaktif - Klik untuk Pilih Lokasi Gangguan")
    
    interactive_map = create_interactive_map(
        st.session_state.gdf_nearby, 
        st.session_state.gangguan_coords, 
        zoom_level
    )
    
    map_data = st_folium(interactive_map, width=1200, height=500, key="interactive_map")
    
    # Process map click
    if map_data and map_data.get("last_clicked"):
        click_data = map_data["last_clicked"]
        current_click = (click_data['lat'], click_data['lng'])
        last_click = st.session_state.last_click_coords
        
        if last_click is None or abs(current_click[0] - last_click[0]) > 0.0001 or abs(current_click[1] - last_click[1]) > 0.0001:
            st.session_state.last_click_coords = current_click
            st.session_state.map_click_data = click_data
            
            with st.spinner("Memproses lokasi yang dipilih..."):
                success = analyze_from_map_click(click_data, radius_km)
                if success:
                    st.success("✅ Analisis selesai!")
            st.rerun()
    
    # Manual analysis
    if analyze_btn:
        st.session_state.analysis_done = True
        st.session_state.gangguan_coords = [lat, lon]
        
        gangguan_point = Point(lon, lat)
        
        with st.spinner(f"Mencari features dalam radius {radius_km} km..."):
            data_to_use = st.session_state.gdf_filtered if st.session_state.gdf_filtered is not None else st.session_state.gdf_master
            st.session_state.gdf_nearby = filter_features_nearby(
                data_to_use, 
                gangguan_point, 
                radius_km
            )
        st.rerun()
    
    # Show click info
    if st.session_state.map_click_data:
        st.info(f"📍 **Lokasi terpilih dari peta:** Lat: {st.session_state.map_click_data['lat']:.6f}, Lon: {st.session_state.map_click_data['lng']:.6f}")
    
    # Show analysis results
    if st.session_state.analysis_done and st.session_state.gangguan_coords:
        st.header(f"📊 Hasil Analisis Gangguan")
        
        # Show folder filter info
        if st.session_state.selected_folders:
            st.info(f"**Folder aktif:** {', '.join(st.session_state.selected_folders)}")
        
        if st.session_state.map_click_data:
            st.write(f"**Sumber:** Klik Peta | **Lokasi:** {st.session_state.gangguan_coords[0]:.6f}, {st.session_state.gangguan_coords[1]:.6f}")
        else:
            st.write(f"**Sumber:** Input Manual | **Lokasi:** {st.session_state.gangguan_coords[0]:.6f}, {st.session_state.gangguan_coords[1]:.6f}")
        
        st.write(f"**Radius:** {radius_km} km")
        
        # Statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            feature_count = len(st.session_state.gdf_nearby) if st.session_state.gdf_nearby is not None else 0
            st.metric("Features Ditemukan", feature_count)
        
        with col2:
            if st.session_state.gdf_nearby is not None and not st.session_state.gdf_nearby.empty:
                closest_dist = st.session_state.gdf_nearby['jarak_meter'].iloc[0]
                st.metric("Jarak Terdekat", f"{closest_dist:.0f} m")
            else:
                st.metric("Jarak Terdekat", "Tidak ada")
        
        with col3:
            if st.session_state.gdf_nearby is not None and not st.session_state.gdf_nearby.empty:
                types = st.session_state.gdf_nearby.geometry.type.unique()
                st.metric("Tipe Geometri", len(types))
            else:
                st.metric("Tipe Geometri", "0")
        
        with col4:
            st.metric("Radius Pencarian", f"{radius_km} km")
        
        # Results table
        if st.session_state.gdf_nearby is not None and not st.session_state.gdf_nearby.empty:
            st.header("📋 Detail Features Terdekat")
            
            display_df = st.session_state.gdf_nearby.copy()
            cols_to_display = [col for col in display_df.columns if col != 'geometry']
            
            # Find name column
            name_cols = [col for col in cols_to_display if 'name' in col.lower()]
            if name_cols:
                name_col = name_cols[0]
                display_columns = [name_col, 'jarak_meter'] + [col for col in cols_to_display if col not in [name_col, 'jarak_meter']]
            else:
                display_columns = ['jarak_meter'] + [col for col in cols_to_display if col != 'jarak_meter']
            
            st.dataframe(display_df[display_columns], use_container_width=True)
            
            # Download
            csv_data = display_df[display_columns].to_csv(index=False)
            st.download_button(
                label="📥 Download Hasil Analisis (CSV)",
                data=csv_data,
                file_name=f"gangguan_{st.session_state.gangguan_coords[0]:.6f}_{st.session_state.gangguan_coords[1]:.6f}_{datetime.now().strftime('%H%M')}.csv",
                mime="text/csv"
            )
        else:
            st.warning(f"⚠️ Tidak ada features ditemukan dalam radius {radius_km} km.")
    
    else:
        # Initial view
        st.markdown("""
        ## 📁 Sistem GIS dengan Folder Selection
        
        **Cara penggunaan:**
        1. **Load KML Data** dari sidebar
        2. **Pilih folder** yang ingin dianalisis
        3. **Klik di peta** untuk pilih lokasi gangguan
        4. **Lihat hasil** analisis per folder
        """)

else:
    st.info("""
    ## 📁 Welcome to GIS KML Folder Selector
    
    **Silakan:**
    1. Klik **"Load KML Data"** di sidebar untuk memuat data
    2. Pilih folder yang ingin dianalisis
    3. Klik di peta untuk memilih lokasi gangguan
    
    **Fitur:**
    - 📂 Pilih data per folder dari KML
    - 🎯 Filter analisis berdasarkan area tertentu
    - 🗺️ Klik peta untuk input lokasi
    - 📊 Hasil analisis spesifik per folder
    """)

st.markdown("---")
st.markdown("**GIS KML Folder Selector** © 2024 | Folder-based Analysis")
