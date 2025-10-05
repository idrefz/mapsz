import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import numpy as np
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
    .clicked-info {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2196f3;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

def parse_kml_with_folders(kml_content):
    """Parse KML dengan struktur folder dan semua tipe geometri"""
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
            
            # Tentukan type dari name/description/folder
            feature_type = "Other"
            type_keywords = {
                'monumen': 'Monument',
                'monas': 'Monument', 
                'taman': 'Park',
                'park': 'Park',
                'museum': 'Museum',
                'sejarah': 'Historical',
                'historical': 'Historical',
                'jalan': 'Road',
                'road': 'Road',
                'street': 'Road',
                'sungai': 'River',
                'river': 'River',
                'batas': 'Boundary',
                'boundary': 'Boundary'
            }
            
            for keyword, type_name in type_keywords.items():
                if keyword in name.lower() or keyword in description.lower() or keyword in folder_path.lower():
                    feature_type = type_name
                    break
            
            features.append({
                'name': name,
                'description': description,
                'type': feature_type,
                'geometry_type': geometry_type,
                'coordinates': coordinates,
                'folder': folder_path,
                'full_path': folder_path + " > " + name if folder_path else name
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

def create_sample_data():
    """Membuat data sampel dengan berbagai tipe geometri"""
    features = []
    
    # Points
    points_data = [
        {'name': 'Monumen Nasional', 'type': 'Monument', 'lat': -6.1754, 'lng': 106.8272, 'folder': 'Landmark > Monumen'},
        {'name': 'Bundaran HI', 'type': 'Landmark', 'lat': -6.1963, 'lng': 106.8229, 'folder': 'Landmark'},
        {'name': 'Taman Mini', 'type': 'Park', 'lat': -6.3024, 'lng': 106.8952, 'folder': 'Wisata > Taman'},
    ]
    
    for point in points_data:
        features.append({
            'name': point['name'],
            'description': f"Deskripsi {point['name']}",
            'type': point['type'],
            'geometry_type': 'Point',
            'coordinates': [{'lng': point['lng'], 'lat': point['lat']}],
            'folder': point['folder'],
            'full_path': point['folder'] + " > " + point['name']
        })
    
    # LineStrings (jalan)
    lines_data = [
        {
            'name': 'Jalan Sudirman', 
            'type': 'Road',
            'coordinates': [
                {'lng': 106.815, 'lat': -6.190}, {'lng': 106.820, 'lat': -6.195},
                {'lng': 106.825, 'lat': -6.200}, {'lng': 106.830, 'lat': -6.205}
            ],
            'folder': 'Infrastruktur > Jalan'
        },
        {
            'name': 'Jalan Thamrin',
            'type': 'Road', 
            'coordinates': [
                {'lng': 106.818, 'lat': -6.185}, {'lng': 106.823, 'lat': -6.190},
                {'lng': 106.828, 'lat': -6.195}
            ],
            'folder': 'Infrastruktur > Jalan'
        }
    ]
    
    for line in lines_data:
        features.append({
            'name': line['name'],
            'description': f"Jalan utama {line['name']}",
            'type': line['type'],
            'geometry_type': 'LineString',
            'coordinates': line['coordinates'],
            'folder': line['folder'],
            'full_path': line['folder'] + " > " + line['name']
        })
    
    return pd.DataFrame(features)

def create_base_map(location=[-6.2088, 106.8456], zoom_start=11):
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
        'Road': 'blue',
        'River': 'lightblue',
        'Boundary': 'orange',
        'Historical': 'purple',
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
        'Road': 'road',
        'River': 'tint',
        'Boundary': 'resize-horizontal',
        'Historical': 'bookmark',
        'Museum': 'education',
        'Other': 'info-sign'
    }
    return icon_map.get(feature_type, 'info-sign')

def main():
    # Header
    st.markdown('<h1 class="main-header">🌍 Web GIS dengan KML Interaktif</h1>', unsafe_allow_html=True)
    
    # Initialize session state untuk data yang diklik
    if 'clicked_feature' not in st.session_state:
        st.session_state.clicked_feature = None
    
    # Sidebar
    with st.sidebar:
        st.markdown('<h2 class="sidebar-header">📁 Upload File KML</h2>', unsafe_allow_html=True)
        
        # Upload file KML
        uploaded_file = st.file_uploader("Pilih file KML", type=['kml'], key="kml_uploader")
        
        df = None
        
        if uploaded_file is not None:
            # Baca konten file
            kml_content = uploaded_file.read().decode('utf-8')
            df = parse_kml_with_folders(kml_content)
            if df is not None:
                st.success(f"✅ File KML berhasil dimuat! {len(df)} fitur ditemukan.")
        else:
            # Coba baca file zxcmcnc.kml jika ada
            try:
                if os.path.exists('zxcmcnc.kml'):
                    with open('zxcmcnc.kml', 'r', encoding='utf-8') as f:
                        kml_content = f.read()
                    df = parse_kml_with_folders(kml_content)
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
            show_lines = st.checkbox("Tampilkan LineString", value=True)
            show_popups = st.checkbox("Tampilkan Popup Info", value=True)
            show_heatmap = st.checkbox("Tampilkan Heatmap", value=False)
            
            # Filter berdasarkan folder
            st.markdown("**Filter berdasarkan Folder:**")
            if 'folder' in df.columns:
                all_folders = ["Semua Folder"] + sorted(df['folder'].unique().tolist())
                selected_folder = st.selectbox(
                    "Pilih folder:",
                    all_folders
                )
            else:
                selected_folder = "Semua Folder"
            
            # Filter berdasarkan jenis geometri
            st.markdown("**Filter berdasarkan Tipe Geometri:**")
            geometry_types = ["Semua"] + sorted(df['geometry_type'].unique().tolist())
            selected_geometry = st.selectbox(
                "Pilih tipe geometri:",
                geometry_types
            )
            
            # Filter berdasarkan jenis fitur
            st.markdown("**Filter berdasarkan Jenis Fitur:**")
            feature_types = ["Semua"] + sorted(df['type'].unique().tolist())
            selected_feature_type = st.selectbox(
                "Pilih jenis fitur:",
                feature_types
            )
    
    # Layout utama
    if df is not None:
        # Filter data
        filtered_df = df.copy()
        
        # Filter berdasarkan folder
        if selected_folder != "Semua Folder":
            filtered_df = filtered_df[filtered_df['folder'] == selected_folder]
        
        # Filter berdasarkan tipe geometri
        if selected_geometry != "Semua":
            filtered_df = filtered_df[filtered_df['geometry_type'] == selected_geometry]
        
        # Filter berdasarkan jenis fitur
        if selected_feature_type != "Semua":
            filtered_df = filtered_df[filtered_df['type'] == selected_feature_type]
        
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
                feature_data = row.to_dict()
                
                # Konten popup
                popup_content = f"""
                <div style='min-width:250px'>
                    <h4>{row['name']}</h4>
                    <b>Type:</b> {row['type']}<br>
                    <b>Geometry:</b> {row['geometry_type']}<br>
                    <b>Folder:</b> {row['folder']}<br>
                    <button onclick="window.parent.postMessage({{'type': 'feature_click', 'data': {feature_data}}}, '*')">
                        Lihat Detail
                    </button>
                </div>
                """
                
                # Handle different geometry types
                if row['geometry_type'] == 'Point' and show_markers and len(row['coordinates']) > 0:
                    # Tambahkan marker untuk Point
                    coord = row['coordinates'][0]
                    color = get_color_from_type(row['type'])
                    icon = get_icon_from_type(row['type'])
                    
                    marker = folium.Marker(
                        location=[coord['lat'], coord['lng']],
                        popup=folium.Popup(popup_content, max_width=300) if show_popups else None,
                        tooltip=row['name'],
                        icon=folium.Icon(color=color, icon=icon, prefix='glyphicon')
                    )
                    
                    # Tambahkan click handler
                    marker.add_to(m)
                
                elif row['geometry_type'] == 'LineString' and show_lines and len(row['coordinates']) > 1:
                    # Tambahkan polyline untuk LineString
                    line_coords = [[coord['lat'], coord['lng']] for coord in row['coordinates']]
                    
                    folium.PolyLine(
                        locations=line_coords,
                        popup=folium.Popup(popup_content, max_width=300) if show_popups else None,
                        tooltip=row['name'],
                        color=get_color_from_type(row['type']),
                        weight=4,
                        opacity=0.7
                    ).add_to(m)
                
                elif row['geometry_type'] == 'Polygon' and len(row['coordinates']) > 2:
                    # Tambahkan polygon
                    poly_coords = [[coord['lat'], coord['lng']] for coord in row['coordinates']]
                    
                    folium.Polygon(
                        locations=poly_coords,
                        popup=folium.Popup(popup_content, max_width=300) if show_popups else None,
                        tooltip=row['name'],
                        color=get_color_from_type(row['type']),
                        fill=True,
                        fillOpacity=0.2,
                        weight=2
                    ).add_to(m)
            
            # Tambahkan heatmap untuk points saja
            if show_heatmap:
                from folium.plugins import HeatMap
                heat_data = []
                for idx, row in filtered_df.iterrows():
                    if row['geometry_type'] == 'Point' and len(row['coordinates']) > 0:
                        coord = row['coordinates'][0]
                        heat_data.append([coord['lat'], coord['lng'], 1])
                
                if heat_data:
                    HeatMap(heat_data, radius=15, blur=10).add_to(m)
            
            # Tambahkan kontrol
            from folium.plugins import MeasureControl, Fullscreen
            MeasureControl().add_to(m)
            Fullscreen().add_to(m)
            
            # Tampilkan peta
            st.markdown("### 🗺️ Peta Interaktif")
            map_data = st_folium(
                m, 
                width=700, 
                height=600, 
                key="main_map",
                returned_objects=["last_clicked", "last_object_clicked"]
            )
            
            # Handle feature clicks dari popup
            if map_data.get('last_object_clicked'):
                clicked_popup = map_data['last_object_clicked'].get('popup')
                if clicked_popup:
                    # Simpan data yang diklik ke session state
                    try:
                        # Extract data dari popup (ini adalah simplified version)
                        # Dalam implementasi real, Anda perlu mengirim data melalui JavaScript
                        st.session_state.clicked_feature = {
                            'name': 'Feature dari Peta',
                            'coordinates': map_data['last_clicked']
                        }
                    except:
                        pass
            
            # Info klik koordinat
            if map_data.get('last_clicked'):
                st.info(f"📍 Koordinat terklik: {map_data['last_clicked']}")
        
        with col2:
            st.markdown("### 📊 Informasi Data")
            
            # Tampilkan info feature yang diklik
            if st.session_state.clicked_feature:
                st.markdown("#### 🎯 Fitur yang Diklik")
                feature = st.session_state.clicked_feature
                st.markdown(f"""
                <div class="clicked-info">
                    <h4>{feature.get('name', 'Unknown Feature')}</h4>
                    <b>Type:</b> {feature.get('type', 'Unknown')}<br>
                    <b>Geometry:</b> {feature.get('geometry_type', 'Unknown')}<br>
                    <b>Folder:</b> {feature.get('folder', 'Unknown')}<br>
                    <b>Coordinates:</b> {feature.get('coordinates', 'No coordinates')}
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("Clear Selection"):
                    st.session_state.clicked_feature = None
                    st.rerun()
            else:
                st.info("👆 Klik pada fitur di peta untuk melihat detail")
            
            # Metrics
            col_metric1, col_metric2 = st.columns(2)
            with col_metric1:
                st.metric("Total Fitur", len(df))
                st.metric("Points", len(df[df['geometry_type'] == 'Point']))
            
            with col_metric2:
                st.metric("Ditampilkan", len(filtered_df))
                st.metric("Lines", len(df[df['geometry_type'] == 'LineString']))
            
            # Statistik folder
            st.markdown("#### 📁 Struktur Folder")
            if 'folder' in df.columns:
                folder_stats = df['folder'].value_counts().head(5)
                for folder, count in folder_stats.items():
                    st.write(f"📂 **{folder}**: {count} fitur")
            
            # Statistik tipe geometri
            st.markdown("#### 📐 Tipe Geometri")
            geom_stats = df['geometry_type'].value_counts()
            for geom_type, count in geom_stats.items():
                st.write(f"🔷 **{geom_type}**: {count} fitur")
            
            # Daftar fitur yang ditampilkan
            st.markdown("#### 🎯 Fitur yang Ditampilkan")
            for idx, row in filtered_df.head(6).iterrows():
                icon = "📍" if row['geometry_type'] == 'Point' else "📏" if row['geometry_type'] == 'LineString' else "🔷"
                st.markdown(f"""
                <div class="feature-item">
                    {icon} <b>{row['name']}</b><br>
                    <small>{row['type']} | {row['geometry_type']} | {row['folder']}</small>
                </div>
                """, unsafe_allow_html=True)
            
            if len(filtered_df) > 6:
                st.info(f"Menampilkan 6 dari {len(filtered_df)} fitur")
    
    else:
        # Tampilan awal
        st.info("""
        ## 📝 Instruksi Penggunaan
        
        1. **Upload file KML** Anda melalui sidebar
        2. Atau letakkan file `zxcmcnc.kml` di folder yang sama
        3. Atau gunakan **data sampel**
        
        ### 🆕 Fitur Baru:
        - ✅ **Info saat diklik** - Detail fitur yang diklik
        - ✅ **LineString support** - Menampilkan garis/jalan
        - ✅ **Filter folder** - Pilih data berdasarkan struktur folder KML
        - ✅ **Multiple geometry types** - Point, LineString, Polygon
        """)
        
        # Peta kosong
        m = create_base_map()
        st_folium(m, width=800, height=500)

# JavaScript untuk handle click events
st.markdown("""
<script>
window.addEventListener('message', function(event) {
    if (event.data.type === 'feature_click') {
        // Handle feature click dari popup
        console.log('Feature clicked:', event.data.data);
    }
});
</script>
""", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
