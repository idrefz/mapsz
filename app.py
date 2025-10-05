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
    page_title="GIS KML Folder Viewer",
    page_icon="📁",
    layout="wide"
)

# Konfigurasi path KML master
KML_MASTER_PATH = "zxcmcnc.kml"

# Initialize session state
if 'gdf_master' not in st.session_state:
    st.session_state.gdf_master = None
if 'available_folders' not in st.session_state:
    st.session_state.available_folders = []
if 'selected_folder' not in st.session_state:
    st.session_state.selected_folder = None
if 'folder_features' not in st.session_state:
    st.session_state.folder_features = {}
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

# Fungsi untuk extract folders dan features dari KML
def extract_folders_and_features(file_path):
    """Extract semua folder dan features dari file KML"""
    folders = {}
    all_features = []
    
    try:
        # Method 1: Parsing manual XML untuk struktur folder
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
                    feature_data = extract_feature_from_placemark(placemark, ns)
                    if feature_data:
                        feature_data['folder'] = folder_name
                        folders[folder_name].append(feature_data)
                        all_features.append(feature_data)
        
        # Jika tidak ada folder, anggap semua features dalam satu folder
        if not folders:
            folder_name = "All Features"
            folders[folder_name] = []
            
            # Extract semua Placemark langsung
            for placemark in root.findall('.//kml:Placemark', ns):
                feature_data = extract_feature_from_placemark(placemark, ns)
                if feature_data:
                    feature_data['folder'] = folder_name
                    folders[folder_name].append(feature_data)
                    all_features.append(feature_data)
        
        return folders, all_features
        
    except Exception as e:
        st.warning(f"Folder extraction warning: {e}")
        # Fallback: load dengan geopandas dan buat folder berdasarkan geometry type
        try:
            gdf = gpd.read_file(file_path, driver='KML')
            if not gdf.empty:
                folder_name = "All Features"
                folders[folder_name] = []
                
                for idx, row in gdf.iterrows():
                    feature_data = {
                        'name': row.get('name', f'Feature {idx}'),
                        'description': row.get('description', ''),
                        'geometry': row.geometry,
                        'folder': folder_name
                    }
                    folders[folder_name].append(feature_data)
                    all_features.append(feature_data)
                
                return folders, all_features
        except Exception as e2:
            st.error(f"Fallback method also failed: {e2}")
        
        return {}, []

def extract_feature_from_placemark(placemark, ns):
    """Extract feature data dari placemark"""
    try:
        name_elem = placemark.find('kml:name', ns)
        name = name_elem.text if name_elem is not None else "Unnamed"
        
        description_elem = placemark.find('kml:description', ns)
        description = description_elem.text if description_elem is not None else ""
        
        geometry = None
        
        # Cek LineString
        linestring = placemark.find('.//kml:LineString', ns)
        if linestring is not None:
            coordinates = linestring.find('kml:coordinates', ns)
            if coordinates is not None and coordinates.text:
                coords_list = []
                for coord in coordinates.text.strip().split():
                    if coord:
                        try:
                            parts = coord.split(',')
                            lon, lat = float(parts[0]), float(parts[1])
                            coords_list.append((lon, lat))
                        except:
                            continue
                
                if len(coords_list) > 1:
                    geometry = LineString(coords_list)
        
        # Cek Point
        point = placemark.find('.//kml:Point', ns)
        if point is not None:
            coordinates = point.find('kml:coordinates', ns)
            if coordinates is not None and coordinates.text:
                try:
                    parts = coordinates.text.strip().split(',')
                    lon, lat = float(parts[0]), float(parts[1])
                    geometry = Point(lon, lat)
                except:
                    pass
        
        # Cek Polygon
        polygon = placemark.find('.//kml:Polygon', ns)
        if polygon is not None:
            outer = polygon.find('.//kml:outerBoundaryIs', ns)
            if outer is not None:
                coordinates = outer.find('.//kml:coordinates', ns)
                if coordinates is not None and coordinates.text:
                    coords_list = []
                    for coord in coordinates.text.strip().split():
                        if coord:
                            try:
                                parts = coord.split(',')
                                lon, lat = float(parts[0]), float(parts[1])
                                coords_list.append((lon, lat))
                            except:
                                continue
                    
                    if len(coords_list) > 2:
                        geometry = Polygon(coords_list)
        
        if geometry is not None:
            return {
                'name': name,
                'description': description,
                'geometry': geometry
            }
        
        return None
        
    except Exception as e:
        return None

# Fungsi untuk load KML dengan folder support
def load_kml_with_folder_view(file_path):
    """Load KML dengan support view per folder"""
    try:
        folders, all_features = extract_folders_and_features(file_path)
        
        if not folders:
            st.error("❌ Tidak ada folder atau features yang ditemukan dalam KML")
            return None, {}, []
        
        # Convert semua features ke GeoDataFrame
        if all_features:
            gdf = gpd.GeoDataFrame(all_features, crs="EPSG:4326")
            st.success(f"✅ Loaded {len(gdf)} features dalam {len(folders)} folder")
            return gdf, folders, all_features
        else:
            st.error("❌ Tidak ada features yang berhasil diekstrak")
            return None, {}, []
            
    except Exception as e:
        st.error(f"❌ Error loading KML: {e}")
        return None, {}, []

def get_features_by_folder(folder_name, folders_data):
    """Dapatkan features untuk folder tertentu"""
    if folder_name in folders_data:
        return folders_data[folder_name]
    return []

def clean_geometry(gdf):
    """Membersihkan geometry"""
    try:
        gdf = gdf[gdf.geometry.notna()]
        gdf = gdf[~gdf.geometry.is_empty]
        return gdf
    except Exception as e:
        st.warning(f"Geometry cleaning warning: {e}")
        return gdf

def filter_features_nearby(features_list, center_point, radius_km=5):
    """Filter features dalam radius tertentu dari list features"""
    try:
        if not features_list:
            return []
        
        buffer_degrees = radius_km / 111
        buffer_zone = center_point.buffer(buffer_degrees)
        
        nearby_features = []
        
        for feature in features_list:
            try:
                if feature['geometry'].intersects(buffer_zone):
                    # Hitung jarak
                    distance = center_point.distance(feature['geometry']) * 111000
                    feature_copy = feature.copy()
                    feature_copy['jarak_meter'] = distance
                    nearby_features.append(feature_copy)
            except:
                continue
        
        # Sort by distance
        nearby_features.sort(key=lambda x: x['jarak_meter'])
        
        return nearby_features
        
    except Exception as e:
        st.error(f"Error filtering: {e}")
        return []

def create_detailed_popup(feature):
    """Membuat popup detail untuk feature"""
    try:
        popup_html = "<div style='max-width: 350px; max-height: 400px; overflow-y: auto;'>"
        popup_html += "<h4 style='margin-bottom: 10px; color: #1f77b4;'>📋 Detail Feature</h4>"
        
        # Basic info
        popup_html += f"""
        <div style='margin-bottom: 8px; border-bottom: 1px solid #eee; padding-bottom: 5px;'>
            <strong style='color: #333;'>Nama:</strong><br>
            <span style='color: #666; word-wrap: break-word;'>{feature.get('name', 'Unnamed')}</span>
        </div>
        """
        
        if feature.get('description'):
            desc = feature['description']
            if len(desc) > 150:
                desc = desc[:150] + "..."
            popup_html += f"""
            <div style='margin-bottom: 8px; border-bottom: 1px solid #eee; padding-bottom: 5px;'>
                <strong style='color: #333;'>Deskripsi:</strong><br>
                <span style='color: #666; word-wrap: break-word;'>{desc}</span>
            </div>
            """
        
        if feature.get('folder'):
            popup_html += f"""
            <div style='margin-bottom: 8px; border-bottom: 1px solid #eee; padding-bottom: 5px;'>
                <strong style='color: #333;'>Folder:</strong><br>
                <span style='color: #666; word-wrap: break-word;'>{feature['folder']}</span>
            </div>
            """
        
        geometry_type = feature['geometry'].geom_type if 'geometry' in feature else 'Unknown'
        jarak = feature.get('jarak_meter', 'N/A')
        
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

def create_interactive_map(selected_features, gangguan_coords, zoom=15):
    """Membuat peta interaktif dengan features yang dipilih"""
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
        
        # Tambahkan features dari folder yang dipilih
        if selected_features:
            for feature in selected_features:
                try:
                    geometry = feature['geometry']
                    
                    if geometry.geom_type == 'Point':
                        folium.Marker(
                            location=[geometry.y, geometry.x],
                            popup=folium.Popup(create_detailed_popup(feature), max_width=400),
                            icon=folium.Icon(color='blue', icon='info-sign')
                        ).add_to(m)
                    
                    elif geometry.geom_type in ['LineString', 'MultiLineString']:
                        folium.GeoJson(
                            geometry.__geo_interface__,
                            style_function=lambda x: {'color': 'green', 'weight': 4, 'opacity': 0.8},
                            popup=folium.Popup(create_detailed_popup(feature), max_width=400)
                        ).add_to(m)
                    
                    elif geometry.geom_type in ['Polygon', 'MultiPolygon']:
                        folium.GeoJson(
                            geometry.__geo_interface__,
                            style_function=lambda x: {'fillColor': 'orange', 'color': 'orange', 'weight': 2, 'fillOpacity': 0.3},
                            popup=folium.Popup(create_detailed_popup(feature), max_width=400)
                        ).add_to(m)
                        
                except Exception as e:
                    continue
        
        return m
        
    except Exception as e:
        st.error(f"Map creation error: {e}")
        return folium.Map(location=[-6.2, 106.8], zoom_start=10)

def analyze_from_map_click(click_data, radius_km, current_features):
    """Analisis dari klik peta"""
    try:
        if click_data and 'lat' in click_data and 'lng' in click_data:
            lat = click_data['lat']
            lng = click_data['lng']
            
            st.session_state.gangguan_coords = [lat, lng]
            st.session_state.analysis_done = True
            
            gangguan_point = Point(lng, lat)
            
            with st.spinner(f"Mencari features dalam radius {radius_km} km..."):
                st.session_state.gdf_nearby = filter_features_nearby(
                    current_features, 
                    gangguan_point, 
                    radius_km
                )
            
            return True
        return False
    except Exception as e:
        st.error(f"Analysis error: {e}")
        return False

# UI Streamlit
st.title("📁 GIS KML Folder Viewer")
st.markdown("**Pilih folder untuk dilihat di peta → Analisis per area gangguan**")

# Sidebar
with st.sidebar:
    st.header("📁 Folder Selection")
    st.markdown("---")
    
    # Load KML data
    if st.button("🔄 Load KML Data", type="primary", use_container_width=True):
        with st.spinner("Loading KML data dan extracting folders..."):
            st.session_state.gdf_master, st.session_state.folder_features, st.session_state.all_features = load_kml_with_folder_view(KML_MASTER_PATH)
            if st.session_state.gdf_master is not None:
                st.session_state.available_folders = list(st.session_state.folder_features.keys())
                if st.session_state.available_folders:
                    st.session_state.selected_folder = st.session_state.available_folders[0]
                st.success(f"✅ Loaded {len(st.session_state.all_features)} features dalam {len(st.session_state.available_folders)} folder")
    
    st.markdown("---")
    
    # Folder selection
    if st.session_state.available_folders:
        st.subheader("📂 Pilih Folder untuk Dilihat")
        
        selected = st.selectbox(
            "Pilih folder:",
            options=st.session_state.available_folders,
            index=st.session_state.available_folders.index(st.session_state.selected_folder) if st.session_state.selected_folder in st.session_state.available_folders else 0,
            key="folder_selector"
        )
        
        if selected != st.session_state.selected_folder:
            st.session_state.selected_folder = selected
            st.rerun()
        
        # Show folder info
        if st.session_state.selected_folder:
            features_in_folder = st.session_state.folder_features[st.session_state.selected_folder]
            st.info(f"**{st.session_state.selected_folder}** - {len(features_in_folder)} features")
            
            # Show feature list in folder
            with st.expander("📋 Lihat Features dalam Folder"):
                for i, feature in enumerate(features_in_folder[:20]):  # Limit to first 20
                    st.write(f"{i+1}. {feature.get('name', 'Unnamed')}")
                if len(features_in_folder) > 20:
                    st.write(f"... dan {len(features_in_folder) - 20} features lainnya")
    
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
        if st.button("🔄 Reset View", use_container_width=True):
            for key in ['analysis_done', 'gdf_nearby', 'gangguan_coords', 'map_click_data', 'last_click_coords']:
                if key in st.session_state:
                    st.session_state[key] = None
            st.rerun()
    
    st.markdown("---")
    zoom_level = st.slider("Zoom Level Peta", 10, 18, 15, key="zoom_input")

# Main content
if st.session_state.gdf_master is not None and st.session_state.selected_folder:
    # Get current folder features
    current_features = get_features_by_folder(st.session_state.selected_folder, st.session_state.folder_features)
    
    # Show current selection info
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Folder", len(st.session_state.available_folders))
    
    with col2:
        st.metric("Folder Dipilih", st.session_state.selected_folder)
    
    with col3:
        st.metric("Features dalam Folder", len(current_features))
    
    # Peta interaktif - hanya show features dari folder yang dipilih
    st.header(f"🗺️ Peta - Folder: {st.session_state.selected_folder}")
    
    interactive_map = create_interactive_map(
        current_features, 
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
                success = analyze_from_map_click(click_data, radius_km, current_features)
                if success:
                    st.success("✅ Analisis selesai!")
            st.rerun()
    
    # Manual analysis
    if analyze_btn:
        st.session_state.analysis_done = True
        st.session_state.gangguan_coords = [lat, lon]
        
        gangguan_point = Point(lon, lat)
        
        with st.spinner(f"Mencari features dalam radius {radius_km} km..."):
            st.session_state.gdf_nearby = filter_features_nearby(
                current_features, 
                gangguan_point, 
                radius_km
            )
        st.rerun()
    
    # Show click info
    if st.session_state.map_click_data:
        st.info(f"📍 **Lokasi terpilih dari peta:** Lat: {st.session_state.map_click_data['lat']:.6f}, Lon: {st.session_state.map_click_data['lng']:.6f}")
    
    # Show analysis results
    if st.session_state.analysis_done and st.session_state.gangguan_coords:
        st.header(f"📊 Hasil Analisis Gangguan - {st.session_state.selected_folder}")
        
        st.info(f"**Folder yang aktif:** {st.session_state.selected_folder}")
        
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
            if st.session_state.gdf_nearby and len(st.session_state.gdf_nearby) > 0:
                closest_dist = st.session_state.gdf_nearby[0]['jarak_meter']
                st.metric("Jarak Terdekat", f"{closest_dist:.0f} m")
            else:
                st.metric("Jarak Terdekat", "Tidak ada")
        
        with col3:
            if st.session_state.gdf_nearby and len(st.session_state.gdf_nearby) > 0:
                types = set(feat['geometry'].geom_type for feat in st.session_state.gdf_nearby)
                st.metric("Tipe Geometri", len(types))
            else:
                st.metric("Tipe Geometri", "0")
        
        with col4:
            st.metric("Radius Pencarian", f"{radius_km} km")
        
        # Results table
        if st.session_state.gdf_nearby and len(st.session_state.gdf_nearby) > 0:
            st.header("📋 Detail Features Terdekat")
            
            # Convert to DataFrame for display
            display_data = []
            for feature in st.session_state.gdf_nearby:
                display_data.append({
                    'Nama': feature.get('name', 'Unnamed'),
                    'Jarak (m)': f"{feature.get('jarak_meter', 0):.0f}",
                    'Tipe Geometry': feature['geometry'].geom_type,
                    'Deskripsi': feature.get('description', '')[:100] + '...' if feature.get('description') and len(feature.get('description')) > 100 else feature.get('description', ''),
                    'Folder': feature.get('folder', '')
                })
            
            display_df = pd.DataFrame(display_data)
            st.dataframe(display_df, use_container_width=True)
            
            # Download
            csv_data = display_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Hasil Analisis (CSV)",
                data=csv_data,
                file_name=f"gangguan_{st.session_state.selected_folder}_{st.session_state.gangguan_coords[0]:.6f}_{st.session_state.gangguan_coords[1]:.6f}_{datetime.now().strftime('%H%M')}.csv",
                mime="text/csv"
            )
        else:
            st.warning(f"⚠️ Tidak ada features ditemukan dalam radius {radius_km} km pada folder {st.session_state.selected_folder}.")
    
    else:
        # Initial view for selected folder
        st.markdown(f"""
        ## 📁 Menampilkan Folder: **{st.session_state.selected_folder}**
        
        **{len(current_features)} features** tersedia dalam folder ini.
        
        **Langkah selanjutnya:**
        1. **Klik di peta** untuk memilih lokasi gangguan
        2. **Atau input koordinat manual** di sidebar
        3. **Lihat hasil analisis** untuk folder ini
        """)

else:
    st.info("""
    ## 📁 Welcome to GIS KML Folder Viewer
    
    **Silakan:**
    1. Klik **"Load KML Data"** di sidebar untuk memuat data
    2. Pilih folder yang ingin dilihat dari dropdown
    3. Features dari folder yang dipilih akan ditampilkan di peta
    4. Klik di peta untuk analisis gangguan
    
    **Fitur:**
    - 📂 Pilih folder untuk dilihat di peta
    - 🗺️ Hanya menampilkan features dari folder yang dipilih
    - 🎯 Analisis gangguan spesifik per folder
    - 📊 Detail features dalam folder
    """)

st.markdown("---")
st.markdown("**GIS KML Folder Viewer** © 2024 | View by Folder")
