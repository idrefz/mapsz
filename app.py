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
    page_title="GIS KML Quick Response",
    page_icon="🚨",
    layout="wide"
)

# Konfigurasi path KML master
KML_MASTER_PATH = "zxcmcnc.kml"

# Initialize session state
if 'gdf_master' not in st.session_state:
    st.session_state.gdf_master = None
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

# Fungsi untuk membaca KML dengan semua metode possible
def load_kml_comprehensive(file_path):
    """Membaca KML dengan semua metode yang mungkin"""
    all_features = []
    
    try:
        # Method 1: Geopandas standard
        try:
            gdf1 = gpd.read_file(file_path, driver='KML')
            if not gdf1.empty:
                st.success(f"✅ Method 1 (Geopandas KML): {len(gdf1)} features")
                all_features.append(gdf1)
        except Exception as e:
            st.warning(f"Method 1 failed: {e}")
        
        # Method 2: Geopandas auto-detect
        try:
            gdf2 = gpd.read_file(file_path)
            if not gdf2.empty and len(gdf2) > 0:
                st.success(f"✅ Method 2 (Geopandas auto): {len(gdf2)} features")
                # Cek jika ini berbeda dari method 1
                if not all_features or len(gdf2) != len(all_features[0]):
                    all_features.append(gdf2)
        except Exception as e:
            st.warning(f"Method 2 failed: {e}")
        
        # Method 3: Fiona dengan multiple layers
        try:
            layers = fiona.listlayers(file_path)
            st.info(f"📁 Layers found: {layers}")
            
            for layer in layers:
                try:
                    gdf_layer = gpd.read_file(file_path, layer=layer)
                    if not gdf_layer.empty:
                        st.success(f"✅ Layer '{layer}': {len(gdf_layer)} features")
                        gdf_layer['source_layer'] = layer
                        all_features.append(gdf_layer)
                except Exception as e:
                    st.warning(f"Layer {layer} failed: {e}")
        except Exception as e:
            st.warning(f"Method 3 (Fiona) failed: {e}")
        
        # Method 4: Manual KML parsing untuk complex structures
        try:
            gdf_manual = parse_kml_manual(file_path)
            if not gdf_manual.empty:
                st.success(f"✅ Method 4 (Manual parse): {len(gdf_manual)} features")
                all_features.append(gdf_manual)
        except Exception as e:
            st.warning(f"Method 4 (Manual) failed: {e}")
        
        # Combine semua features
        if all_features:
            combined_gdf = gpd.GeoDataFrame(pd.concat(all_features, ignore_index=True))
            
            # Remove duplicates based on geometry
            combined_gdf = combined_gdf.drop_duplicates(subset=['geometry'])
            
            st.success(f"🎉 TOTAL FEATURES LOADED: {len(combined_gdf)}")
            return combined_gdf
        else:
            st.error("❌ All methods failed to read KML")
            return None
            
    except Exception as e:
        st.error(f"❌ Comprehensive KML reading failed: {e}")
        return None

def parse_kml_manual(file_path):
    """Manual parsing untuk KML yang kompleks"""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        features = []
        
        # Namespace untuk KML
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        # Find all Placemarks
        for placemark in root.findall('.//kml:Placemark', ns):
            try:
                name = placemark.find('kml:name', ns)
                name_text = name.text if name is not None else "Unnamed"
                
                description = placemark.find('kml:description', ns)
                desc_text = description.text if description is not None else ""
                
                # Cek LineString
                linestring = placemark.find('.//kml:LineString', ns)
                if linestring is not None:
                    coordinates = linestring.find('kml:coordinates', ns)
                    if coordinates is not None and coordinates.text:
                        coords_list = []
                        for coord in coordinates.text.strip().split():
                            if coord:
                                try:
                                    lon, lat, alt = map(float, coord.split(','))
                                    coords_list.append((lon, lat))
                                except:
                                    continue
                        
                        if len(coords_list) > 1:
                            geometry = LineString(coords_list)
                            features.append({
                                'name': name_text,
                                'description': desc_text,
                                'geometry': geometry
                            })
                
                # Cek Point
                point = placemark.find('.//kml:Point', ns)
                if point is not None:
                    coordinates = point.find('kml:coordinates', ns)
                    if coordinates is not None and coordinates.text:
                        try:
                            lon, lat, alt = map(float, coordinates.text.strip().split(','))
                            geometry = Point(lon, lat)
                            features.append({
                                'name': name_text,
                                'description': desc_text,
                                'geometry': geometry
                            })
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
                                        lon, lat, alt = map(float, coord.split(','))
                                        coords_list.append((lon, lat))
                                    except:
                                        continue
                            
                            if len(coords_list) > 2:
                                geometry = Polygon(coords_list)
                                features.append({
                                    'name': name_text,
                                    'description': desc_text,
                                    'geometry': geometry
                                })
                                
            except Exception as e:
                continue  # Skip placemark yang error
        
        if features:
            gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")
            return gdf
        else:
            return gpd.GeoDataFrame()
            
    except Exception as e:
        st.warning(f"Manual parsing failed: {e}")
        return gpd.GeoDataFrame()

def load_master_kml():
    """Memuat KML master dengan approach komprehensif"""
    try:
        if not os.path.exists(KML_MASTER_PATH):
            st.error(f"❌ File tidak ditemukan: {KML_MASTER_PATH}")
            return None
        
        st.info("🔄 Loading KML dengan semua metode...")
        gdf = load_kml_comprehensive(KML_MASTER_PATH)
        
        if gdf is not None and not gdf.empty:
            # Clean data
            gdf = clean_geometry(gdf)
            
            # Show detailed info
            st.success(f"📊 Data berhasil dimuat: {len(gdf)} features")
            
            # Show geometry types
            geom_types = gdf.geometry.type.value_counts()
            st.write("**Jenis Geometry:**")
            for geom_type, count in geom_types.items():
                st.write(f"- {geom_type}: {count} features")
            
            # Show columns info
            st.write(f"**Kolom yang tersedia:** {list(gdf.columns)}")
            
            return gdf
        else:
            st.error("❌ Tidak ada data yang berhasil dimuat")
            return None
            
    except Exception as e:
        st.error(f"❌ Error loading KML: {e}")
        return None

def clean_geometry(gdf):
    """Membersihkan geometry"""
    try:
        # Hapus baris dengan geometry None
        gdf = gdf[gdf.geometry.notna()]
        
        # Hapus geometry yang empty
        gdf = gdf[~gdf.geometry.is_empty]
        
        # Coba fix geometry yang invalid
        def fix_geometry(geom):
            try:
                if not geom.is_valid:
                    return geom.buffer(0)  # Buffer 0 sering memperbaiki invalid geometry
                return geom
            except:
                return None
        
        gdf['geometry'] = gdf.geometry.apply(fix_geometry)
        
        # Hapus lagi yang jadi None setelah fixing
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

def create_interactive_map(gdf_nearby, gangguan_coords, zoom=15, radius_km=5):
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
                html='<div style="background-color: white; padding: 10px; border: 3px solid #007cba; border-radius: 8px; font-size: 14px; font-weight: bold; color: #007cba;">📍 </div>'
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
                popup=f"Area Pencarian ({radius_km} km)"
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
                st.session_state.gdf_nearby = filter_features_nearby(
                    st.session_state.gdf_master, 
                    gangguan_point, 
                    radius_km
                )
            
            return True
        return False
    except Exception as e:
        st.error(f"Analysis error: {e}")
        return False

# UI Streamlit
st.title("🚨 GIS KML Quick Response - ULTIMATE")
st.markdown("**Semua data KML akan terbaca - Pilih lokasi dengan klik peta**")

# Sidebar
with st.sidebar:
    st.header("📍 Input Lokasi Gangguan")
    st.markdown("---")
    
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
        if st.button("🔄 Reset", use_container_width=True):
            for key in ['analysis_done', 'gdf_nearby', 'gangguan_coords', 'map_click_data', 'last_click_coords']:
                if key in st.session_state:
                    st.session_state[key] = None
            st.rerun()
    
    # Force reload button
    if st.button("🔄 Force Reload KML", use_container_width=True):
        if 'gdf_master' in st.session_state:
            st.session_state.gdf_master = None
        st.rerun()
    
    st.markdown("---")
    zoom_level = st.slider("Zoom Level Peta", 10, 18, 15, key="zoom_input")

# Load master KML
if st.session_state.gdf_master is None:
    with st.spinner("🔄 MEMUAT DATA KML... Ini mungkin butuh beberapa detik..."):
        st.session_state.gdf_master = load_master_kml()

# Main content
if st.session_state.gdf_master is not None and not st.session_state.gdf_master.empty:
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
            st.session_state.gdf_nearby = filter_features_nearby(
                st.session_state.gdf_master, 
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
        
        if st.session_state.map_click_data:
            st.write(f"**Sumber:** Klik Peta | **Lokasi:** {st.session_state.gangguan_coords[0]:.6f}, {st.session_state.gangguan_coords[1]:.6f}")
        else:
            st.write(f"**Sumber:** Input Manual | **Lokasi:** {st.session_state.gangguan_coords[0]:.6f}, {st.session_state.gangguan_coords[1]:.6f}")
        
        st.write(f"**Radius:** {radius_km} km")
        
        # Statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            feature_count = len(st.session_state.gdf_nearby) if st.session_state.gdf_nearby is not None else 0
            st.metric("Total Features Ditemukan", feature_count)
        
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
        ## 🎉 SISTEM READY - SEMUA DATA TERBACA!
        
        **Klik di peta untuk mulai analisis gangguan**
        """)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Features", len(st.session_state.gdf_master))
        
        with col2:
            geometry_types = st.session_state.gdf_master.geometry.type.unique()
            st.metric("Jenis Geometri", len(geometry_types))
        
        with col3:
            name_cols = [col for col in st.session_state.gdf_master.columns if 'name' in col.lower()]
            if name_cols:
                named_features = st.session_state.gdf_master[name_cols[0]].notna().sum()
                st.metric("Features Bernama", named_features)

else:
    st.error("""
    ❌ Gagal memuat data KML.
    
    **Coba solusi:**
    1. Pastikan file `zxcmcnc.kml` ada di folder yang sama
    2. Klik tombol **Force Reload KML**
    3. Cek format file KML dengan software lain
    4. Jika masih gagal, coba konversi KML ke format lain
    """)

st.markdown("---")
st.markdown("**GIS Ultimate KML Reader** © 2024 | All Data Loaded Successfully")
