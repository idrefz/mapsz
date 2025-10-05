import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
from io import StringIO
import tempfile
import os
import re

# Konfigurasi halaman
st.set_page_config(
    page_title="Web GIS SERANG Deployment",
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
    .clicked-info {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2196f3;
        margin: 0.5rem 0;
    }
    .folder-structure {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #ffc107;
        margin: 0.5rem 0;
    }
    .deployment-item {
        background-color: #d1ecf1;
        padding: 0.5rem;
        margin: 0.2rem 0;
        border-radius: 5px;
        border-left: 3px solid #17a2b8;
    }
</style>
""", unsafe_allow_html=True)

def parse_kml_with_serang_structure(kml_content):
    """Parse KML dengan struktur folder SERANG Deployment"""
    try:
        features = []
        
        root = ET.fromstring(kml_content)
        
        # Namespace KML
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        def extract_placemark(placemark, folder_path=""):
            """Extract data dari placemark"""
            # Extract name
            name_elem = placemark.find('kml:name', ns)
            name = name_elem.text if name_elem is not None else "Unnamed"
            
            # Extract description
            desc_elem = placemark.find('kml:description', ns)
            description = desc_elem.text if desc_elem is not None else ""
            
            # Extract geometry
            geometry_type = "Unknown"
            coordinates = []
            
            # Cek Point
            point_elem = placemark.find('.//kml:Point', ns)
            if point_elem is not None:
                geometry_type = "Point"
                coords_elem = point_elem.find('kml:coordinates', ns)
                if coords_elem is not None and coords_elem.text:
                    coord_text = coords_elem.text.strip()
                    coords = coord_text.split()
                    if coords:
                        first_coord = coords[0].split(',')
                        if len(first_coord) >= 2:
                            coordinates = [{'lng': float(first_coord[0]), 'lat': float(first_coord[1])}]
            
            # Cek LineString
            line_elem = placemark.find('.//kml:LineString', ns)
            if line_elem is not None:
                geometry_type = "LineString"
                coords_elem = line_elem.find('kml:coordinates', ns)
                if coords_elem is not None and coords_elem.text:
                    coord_text = coords_elem.text.strip()
                    for coord in coord_text.split():
                        parts = coord.split(',')
                        if len(parts) >= 2:
                            coordinates.append({'lng': float(parts[0]), 'lat': float(parts[1])})
            
            # Cek Polygon
            polygon_elem = placemark.find('.//kml:Polygon', ns)
            if polygon_elem is not None:
                geometry_type = "Polygon"
                outer_elem = polygon_elem.find('.//kml:outerBoundaryIs', ns)
                if outer_elem is not None:
                    coords_elem = outer_elem.find('.//kml:coordinates', ns)
                    if coords_elem is not None and coords_elem.text:
                        coord_text = coords_elem.text.strip()
                        for coord in coord_text.split():
                            parts = coord.split(',')
                            if len(parts) >= 2:
                                coordinates.append({'lng': float(parts[0]), 'lat': float(parts[1])})
            
            # Tentukan deployment type berdasarkan nama dan folder
            deployment_type = "Other"
            
            # Pattern matching untuk deployment SERANG
            if re.search(r'MTEL-SERANG-Q3AOP2023-DF002', name) or any(re.search(r'MODF-R04-CLG0-R005-S\d+', name) for coord in coordinates):
                deployment_type = "DF002"
            elif re.search(r'MTEL-SERANG-Q3AOP2023-DF002A', name) or any(re.search(r'MODF-R04-CLG0-R008-S\d+', name) for coord in coordinates):
                deployment_type = "DF002A"
            elif re.search(r'MTEL-SERANG-Q3AOP2023-DF004A', name) or any(re.search(r'MODF-R04-CLG0-R007-S\d+', name) for coord in coordinates):
                deployment_type = "DF004A"
            elif "SERANG" in folder_path.upper():
                deployment_type = "SERANG_Other"
            
            features.append({
                'name': name,
                'description': description,
                'type': deployment_type,
                'geometry_type': geometry_type,
                'coordinates': coordinates,
                'folder': folder_path,
                'full_path': folder_path + " > " + name if folder_path else name,
                'deployment_id': deployment_type
            })
        
        def process_folder(folder_elem, current_path=""):
            """Process folder dan subfolder recursively"""
            folder_name_elem = folder_elem.find('kml:name', ns)
            folder_name = folder_name_elem.text if folder_name_elem is not None else "Unnamed Folder"
            
            new_path = current_path + " > " + folder_name if current_path else folder_name
            
            # Process placemarks dalam folder ini
            for placemark in folder_elem.findall('kml:Placemark', ns):
                extract_placemark(placemark, new_path)
            
            # Process subfolders
            for subfolder in folder_elem.findall('kml:Folder', ns):
                process_folder(subfolder, new_path)
        
        # Process root level placemarks
        for placemark in root.findall('.//kml:Placemark', ns):
            extract_placemark(placemark)
        
        # Process folders
        for folder in root.findall('.//kml:Folder', ns):
            process_folder(folder)
        
        # Buat DataFrame
        if features:
            df = pd.DataFrame(features)
            return df
        else:
            st.warning("Tidak ada fitur yang ditemukan dalam file KML")
            return None
            
    except Exception as e:
        st.error(f"Error parsing KML: {str(e)}")
        return None

def create_serang_sample_data():
    """Membuat data sampel dengan struktur SERANG Deployment"""
    features = []
    
    # DF002 Deployment
    df002_points = [
        {'name': 'MTEL-SERANG-Q3AOP2023-DF002', 'lat': -6.120, 'lng': 106.150, 'site': 'Main Site'},
        {'name': 'MODF-R04-CLG0-R005-S008', 'lat': -6.121, 'lng': 106.151, 'site': 'Site 008'},
        {'name': 'MODF-R04-CLG0-R005-S01', 'lat': -6.122, 'lng': 106.152, 'site': 'Site 01'},
        {'name': 'MODF-R04-CLG0-R005-S03', 'lat': -6.123, 'lng': 106.153, 'site': 'Site 03'},
        {'name': 'MODF-R04-CLG0-R005-S02', 'lat': -6.124, 'lng': 106.154, 'site': 'Site 02'},
    ]
    
    for point in df002_points:
        features.append({
            'name': point['name'],
            'description': f"SERANG Deployment - {point['site']}",
            'type': 'DF002',
            'geometry_type': 'Point',
            'coordinates': [{'lng': point['lng'], 'lat': point['lat']}],
            'folder': 'SERANG > Deployment > DF002',
            'full_path': f"SERANG > Deployment > DF002 > {point['name']}",
            'deployment_id': 'DF002'
        })
    
    # DF002A Deployment
    df002a_points = [
        {'name': 'MTEL-SERANG-Q3AOP2023-DF002A', 'lat': -6.115, 'lng': 106.145, 'site': 'Main Site A'},
        {'name': 'MODF-R04-CLG0-R005-S004', 'lat': -6.116, 'lng': 106.146, 'site': 'Site 004'},
        {'name': 'MODF-R04-CLG0-R008-S01', 'lat': -6.117, 'lng': 106.147, 'site': 'Site 01'},
    ]
    
    for point in df002a_points:
        features.append({
            'name': point['name'],
            'description': f"SERANG Deployment - {point['site']}",
            'type': 'DF002A',
            'geometry_type': 'Point',
            'coordinates': [{'lng': point['lng'], 'lat': point['lat']}],
            'folder': 'SERANG > Deployment > DF002A',
            'full_path': f"SERANG > Deployment > DF002A > {point['name']}",
            'deployment_id': 'DF002A'
        })
    
    # DF004A Deployment
    df004a_points = [
        {'name': 'MTEL-SERANG-Q3AOP2023-DF004A', 'lat': -6.110, 'lng': 106.140, 'site': 'Main Site B'},
        {'name': 'MODF-R04-CLG0-R007-S02', 'lat': -6.111, 'lng': 106.141, 'site': 'Site 02'},
        {'name': 'MODF-R04-CLG0-R007-S03', 'lat': -6.112, 'lng': 106.142, 'site': 'Site 03'},
        {'name': 'MODF-R04-CLG0-R007-S01', 'lat': -6.113, 'lng': 106.143, 'site': 'Site 01'},
    ]
    
    for point in df004a_points:
        features.append({
            'name': point['name'],
            'description': f"SERANG Deployment - {point['site']}",
            'type': 'DF004A',
            'geometry_type': 'Point',
            'coordinates': [{'lng': point['lng'], 'lat': point['lat']}],
            'folder': 'SERANG > Deployment > DF004A',
            'full_path': f"SERANG > Deployment > DF004A > {point['name']}",
            'deployment_id': 'DF004A'
        })
    
    # Tambahkan LineString untuk fiber optic routes
    fiber_routes = [
        {
            'name': 'Fiber Route DF002', 
            'type': 'DF002',
            'coordinates': [
                {'lng': 106.150, 'lat': -6.120}, {'lng': 106.151, 'lat': -6.121},
                {'lng': 106.152, 'lat': -6.122}, {'lng': 106.153, 'lat': -6.123},
                {'lng': 106.154, 'lat': -6.124}
            ],
            'folder': 'SERANG > Deployment > DF002 > Fiber Routes'
        },
        {
            'name': 'Fiber Route DF002A',
            'type': 'DF002A', 
            'coordinates': [
                {'lng': 106.145, 'lat': -6.115}, {'lng': 106.146, 'lat': -6.116},
                {'lng': 106.147, 'lat': -6.117}
            ],
            'folder': 'SERANG > Deployment > DF002A > Fiber Routes'
        }
    ]
    
    for route in fiber_routes:
        features.append({
            'name': route['name'],
            'description': f"Fiber Optic Route - {route['type']}",
            'type': route['type'],
            'geometry_type': 'LineString',
            'coordinates': route['coordinates'],
            'folder': route['folder'],
            'full_path': route['folder'] + " > " + route['name'],
            'deployment_id': route['type']
        })
    
    return pd.DataFrame(features)

def create_base_map(location=[-6.115, 106.148], zoom_start=13):
    """Membuat peta dasar untuk area SERANG"""
    return folium.Map(
        location=location,
        zoom_start=zoom_start,
        tiles='OpenStreetMap',
        control_scale=True
    )

def get_color_from_deployment(deployment_id):
    """Mengembalikan warna berdasarkan deployment ID"""
    color_map = {
        'DF002': 'red',
        'DF002A': 'blue',
        'DF004A': 'green',
        'SERANG_Other': 'orange',
        'Other': 'gray'
    }
    return color_map.get(deployment_id, 'gray')

def get_icon_from_deployment(deployment_id):
    """Mengembalikan ikon berdasarkan deployment ID"""
    icon_map = {
        'DF002': 'signal',
        'DF002A': 'flash',
        'DF004A': 'off',
        'SERANG_Other': 'info-sign',
        'Other': 'question-sign'
    }
    return icon_map.get(deployment_id, 'info-sign')

def main():
    # Header
    st.markdown('<h1 class="main-header">🌍 Web GIS SERANG Deployment</h1>', unsafe_allow_html=True)
    
    # Initialize session state
    if 'clicked_feature' not in st.session_state:
        st.session_state.clicked_feature = None
    
    # Sidebar
    with st.sidebar:
        st.markdown('<h2 class="sidebar-header">📁 Upload File KML SERANG</h2>', unsafe_allow_html=True)
        
        # Upload file KML
        uploaded_file = st.file_uploader("Pilih file KML SERANG", type=['kml'], key="kml_uploader")
        
        df = None
        
        if uploaded_file is not None:
            # Baca konten file
            kml_content = uploaded_file.read().decode('utf-8')
            df = parse_kml_with_serang_structure(kml_content)
            if df is not None:
                st.success(f"✅ File KML berhasil dimuat! {len(df)} fitur ditemukan.")
        else:
            # Coba baca file zxcmcnc.kml jika ada
            try:
                if os.path.exists('zxcmcnc.kml'):
                    with open('zxcmcnc.kml', 'r', encoding='utf-8') as f:
                        kml_content = f.read()
                    df = parse_kml_with_serang_structure(kml_content)
                    if df is not None:
                        st.success(f"✅ File zxcmcnc.kml berhasil dimuat! {len(df)} fitur ditemukan.")
                else:
                    st.info("📝 Upload file KML atau gunakan data sampel SERANG")
            except Exception as e:
                st.warning(f"Tidak bisa membaca zxcmcnc.kml: {str(e)}")
        
        # Tombol data sampel
        if df is None:
            if st.button("Gunakan Data Sampel SERANG"):
                df = create_serang_sample_data()
                st.success(f"✅ Data sampel SERANG dimuat! {len(df)} fitur ditemukan.")
        
        if df is not None:
            st.markdown('<h2 class="sidebar-header">🎛️ Kontrol Deployment</h2>', unsafe_allow_html=True)
            
            # Pilihan layer dasar
            basemap = st.selectbox(
                "Pilih Layer Peta:",
                ["OpenStreetMap", "Satellite", "Terrain", "Dark Mode"]
            )
            
            # Kontrol tampilan
            st.markdown("**Tampilan Fitur:**")
            show_markers = st.checkbox("Tampilkan Site Points", value=True)
            show_lines = st.checkbox("Tampilkan Fiber Routes", value=True)
            show_popups = st.checkbox("Tampilkan Popup Info", value=True)
            
            # Filter berdasarkan Deployment ID
            st.markdown("**Pilih Deployment:**")
            deployment_options = ["Semua Deployment"] + sorted(df['deployment_id'].unique().tolist())
            selected_deployment = st.selectbox(
                "Pilih deployment:",
                deployment_options
            )
            
            # Filter berdasarkan tipe geometri
            st.markdown("**Filter Tipe:**")
            col1, col2 = st.columns(2)
            with col1:
                show_points = st.checkbox("Points", value=True)
            with col2:
                show_linestrings = st.checkbox("Lines", value=True)
            
            # Filter berdasarkan folder SERANG
            st.markdown("**Struktur Folder SERANG:**")
            if 'folder' in df.columns:
                serang_folders = [f for f in df['folder'].unique() if 'SERANG' in f.upper()]
                folder_options = ["Semua Folder"] + sorted(serang_folders)
                selected_folder = st.selectbox(
                    "Pilih folder:",
                    folder_options
                )
            else:
                selected_folder = "Semua Folder"
            
            # Tampilkan struktur deployment
            st.markdown("#### 📋 Struktur Deployment")
            st.markdown("""
            <div class="folder-structure">
            <b>SERANG Deployment Structure:</b><br>
            • DF002 (5 sites)<br>
            • DF002A (3 sites)<br> 
            • DF004A (4 sites)<br>
            • Fiber Routes
            </div>
            """, unsafe_allow_html=True)
    
    # Layout utama
    if df is not None:
        # Filter data
        filtered_df = df.copy()
        
        # Filter berdasarkan deployment
        if selected_deployment != "Semua Deployment":
            filtered_df = filtered_df[filtered_df['deployment_id'] == selected_deployment]
        
        # Filter berdasarkan folder
        if selected_folder != "Semua Folder":
            filtered_df = filtered_df[filtered_df['folder'] == selected_folder]
        
        # Filter berdasarkan tipe geometri
        geometry_filters = []
        if show_points:
            geometry_filters.append('Point')
        if show_linestrings:
            geometry_filters.append('LineString')
        
        if geometry_filters:
            filtered_df = filtered_df[filtered_df['geometry_type'].isin(geometry_filters)]
        
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
            
            # Tambahkan fitur ke peta
            for idx, row in filtered_df.iterrows():
                feature_data = {
                    'name': row['name'],
                    'type': row['type'],
                    'deployment_id': row['deployment_id'],
                    'geometry_type': row['geometry_type'],
                    'folder': row['folder'],
                    'coordinates': row['coordinates']
                }
                
                # Konten popup
                popup_content = f"""
                <div style='min-width:280px; font-family: Arial, sans-serif;'>
                    <h4 style='color: {get_color_from_deployment(row["deployment_id"])}; margin-bottom: 10px;'>
                        {row['name']}
                    </h4>
                    <b>Deployment:</b> {row['deployment_id']}<br>
                    <b>Type:</b> {row['type']}<br>
                    <b>Geometry:</b> {row['geometry_type']}<br>
                    <b>Folder:</b> {row['folder']}<br>
                    <hr style='margin: 8px 0;'>
                    <button onclick="alert('Feature: {row['name']}')" 
                            style='background-color: {get_color_from_deployment(row["deployment_id"])}; 
                                   color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer;'>
                        Lihat Detail
                    </button>
                </div>
                """
                
                # Handle different geometry types
                if row['geometry_type'] == 'Point' and show_markers and len(row['coordinates']) > 0:
                    # Tambahkan marker untuk Point
                    coord = row['coordinates'][0]
                    color = get_color_from_deployment(row['deployment_id'])
                    icon = get_icon_from_deployment(row['deployment_id'])
                    
                    marker = folium.Marker(
                        location=[coord['lat'], coord['lng']],
                        popup=folium.Popup(popup_content, max_width=350) if show_popups else None,
                        tooltip=f"{row['deployment_id']}: {row['name']}",
                        icon=folium.Icon(color=color, icon=icon, prefix='glyphicon')
                    )
                    marker.add_to(m)
                
                elif row['geometry_type'] == 'LineString' and show_lines and len(row['coordinates']) > 1:
                    # Tambahkan polyline untuk LineString
                    line_coords = [[coord['lat'], coord['lng']] for coord in row['coordinates']]
                    
                    folium.PolyLine(
                        locations=line_coords,
                        popup=folium.Popup(popup_content, max_width=350) if show_popups else None,
                        tooltip=f"{row['deployment_id']}: {row['name']}",
                        color=get_color_from_deployment(row['deployment_id']),
                        weight=5,
                        opacity=0.8,
                        dash_array='5, 5' if 'Fiber' in row['name'] else None
                    ).add_to(m)
            
            # Tambahkan kontrol
            from folium.plugins import MeasureControl, Fullscreen
            MeasureControl().add_to(m)
            Fullscreen().add_to(m)
            
            # Tampilkan peta
            st.markdown("### 🗺️ Peta Deployment SERANG")
            map_data = st_folium(
                m, 
                width=700, 
                height=600, 
                key="main_map"
            )
            
            # Handle clicks
            if map_data.get('last_clicked'):
                clicked_coord = map_data['last_clicked']
                # Cari fitur terdekat
                min_distance = float('inf')
                closest_feature = None
                
                for idx, row in filtered_df.iterrows():
                    if row['geometry_type'] == 'Point' and len(row['coordinates']) > 0:
                        coord = row['coordinates'][0]
                        distance = ((coord['lat'] - clicked_coord['lat'])**2 + 
                                  (coord['lng'] - clicked_coord['lng'])**2)**0.5
                        if distance < min_distance and distance < 0.001:  # Threshold ~100m
                            min_distance = distance
                            closest_feature = row
                
                if closest_feature is not None:
                    st.session_state.clicked_feature = closest_feature.to_dict()
            
            # Info klik koordinat
            if map_data.get('last_clicked'):
                st.info(f"📍 Koordinat: {map_data['last_clicked']}")
        
        with col2:
            st.markdown("### 📊 Dashboard SERANG")
            
            # Tampilkan info feature yang diklik
            if st.session_state.clicked_feature:
                feature = st.session_state.clicked_feature
                st.markdown("#### 🎯 Site Terpilih")
                st.markdown(f"""
                <div class="clicked-info">
                    <h4>{feature.get('name', 'Unknown')}</h4>
                    <b>Deployment ID:</b> {feature.get('deployment_id', 'Unknown')}<br>
                    <b>Type:</b> {feature.get('type', 'Unknown')}<br>
                    <b>Geometry:</b> {feature.get('geometry_type', 'Unknown')}<br>
                    <b>Folder:</b> {feature.get('folder', 'Unknown')}<br>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("Clear Selection"):
                    st.session_state.clicked_feature = None
                    st.rerun()
            else:
                st.info("👆 Klik pada site di peta untuk melihat detail")
            
            # Statistics
            st.markdown("#### 📈 Statistik Deployment")
            col_stat1, col_stat2 = st.columns(2)
            
            with col_stat1:
                total_sites = len(df[df['geometry_type'] == 'Point'])
                st.metric("Total Sites", total_sites)
                
                df002_sites = len(df[(df['deployment_id'] == 'DF002') & (df['geometry_type'] == 'Point')])
                st.metric("DF002 Sites", df002_sites)
            
            with col_stat2:
                displayed_sites = len(filtered_df[filtered_df['geometry_type'] == 'Point'])
                st.metric("Ditampilkan", displayed_sites)
                
                df004a_sites = len(df[(df['deployment_id'] == 'DF004A') & (df['geometry_type'] == 'Point')])
                st.metric("DF004A Sites", df004a_sites)
            
            # Deployment breakdown
            st.markdown("#### 🏗️ Breakdown Deployment")
            for deployment in ['DF002', 'DF002A', 'DF004A']:
                deployment_count = len(filtered_df[filtered_df['deployment_id'] == deployment])
                if deployment_count > 0:
                    sites_count = len(filtered_df[(filtered_df['deployment_id'] == deployment) & 
                                                (filtered_df['geometry_type'] == 'Point')])
                    lines_count = len(filtered_df[(filtered_df['deployment_id'] == deployment) & 
                                                (filtered_df['geometry_type'] == 'LineString')])
                    
                    st.markdown(f"""
                    <div class="deployment-item">
                        <b>{deployment}</b>: {deployment_count} fitur<br>
                        <small>📍 {sites_count} sites | 📏 {lines_count} routes</small>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Daftar sites yang ditampilkan
            st.markdown("#### 📋 Daftar Sites")
            points_df = filtered_df[filtered_df['geometry_type'] == 'Point'].head(8)
            
            for idx, row in points_df.iterrows():
                color = get_color_from_deployment(row['deployment_id'])
                st.markdown(f"""
                <div class="feature-item">
                    <span style='color: {color}; font-weight: bold;'>●</span> 
                    <b>{row['name']}</b><br>
                    <small>{row['deployment_id']} | {row['folder'].split('>')[-1].strip()}</small>
                </div>
                """, unsafe_allow_html=True)
            
            if len(points_df) == 0:
                st.info("Tidak ada sites yang sesuai dengan filter")
    
    else:
        # Tampilan awal
        st.info("""
        ## 📝 Web GIS SERANG Deployment
        
        **Struktur Deployment yang Didukung:**
        
        ### 🎯 DF002 Deployment
        - MTEL-SERANG-Q3AOP2023-DF002
        - MODF-R04-CLG0-R005-S008
        - MODF-R04-CLG0-R005-S01  
        - MODF-R04-CLG0-R005-S03
        - MODF-R04-CLG0-R005-S02
        
        ### 🔵 DF002A Deployment  
        - MTEL-SERANG-Q3AOP2023-DF002A
        - MODF-R04-CLG0-R005-S004
        - MODF-R04-CLG0-R008-S01
        
        ### 🟢 DF004A Deployment
        - MTEL-SERANG-Q3AOP2023-DF004A
        - MODF-R04-CLG0-R007-S02
        - MODF-R04-CLG0-R007-S03
        - MODF-R04-CLG0-R007-S01
        
        Upload file KML Anda atau gunakan data sampel!
        """)
        
        # Peta kosong
        m = create_base_map()
        st_folium(m, width=800, height=500)

if __name__ == "__main__":
    main()
