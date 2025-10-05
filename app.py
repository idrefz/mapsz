import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString, Polygon
import tempfile
import os
from datetime import datetime
import math

# Konfigurasi halaman
st.set_page_config(
    page_title="GIS KML Quick Response",
    page_icon="🚨",
    layout="wide"
)

# Konfigurasi path KML master
KML_MASTER_PATH = "zxcmcnc.kml"  # Ganti dengan path file master Anda

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

# Fungsi untuk memuat KML master dengan caching
@st.cache_data(ttl=3600)  # Cache 1 jam
def load_master_kml():
    """Memuat KML master dengan caching untuk performa"""
    try:
        if os.path.exists(KML_MASTER_PATH):
            gdf = gpd.read_file(KML_MASTER_PATH, driver='KML')
            return gdf
        else:
            st.error(f"❌ File master KML tidak ditemukan: {KML_MASTER_PATH}")
            return None
    except Exception as e:
        st.error(f"Error loading master KML: {str(e)}")
        return None

# Fungsi untuk filter features di sekitar titik gangguan
def filter_features_nearby(gdf, center_point, radius_km=5):
    """Filter features dalam radius tertentu dari titik gangguan"""
    try:
        # Buat buffer sekitar titik gangguan (dalam derajat)
        buffer_degrees = radius_km / 111
        buffer_zone = center_point.buffer(buffer_degrees)
        
        # Filter features yang berinterseksi dengan buffer
        nearby_features = gdf[gdf.geometry.intersects(buffer_zone)].copy()
        
        # Hitung jarak untuk setiap feature
        def calculate_distance(geometry):
            try:
                return center_point.distance(geometry) * 111000  # meter
            except:
                return float('inf')
        
        nearby_features['jarak_meter'] = nearby_features.geometry.apply(calculate_distance)
        nearby_features = nearby_features.sort_values('jarak_meter')
        
        return nearby_features
    except Exception as e:
        st.error(f"Error filtering features: {str(e)}")
        return gpd.GeoDataFrame()

# Fungsi untuk membuat popup info yang detail
def create_detailed_popup(row):
    """Membuat popup detail dari semua kolom yang tersedia"""
    popup_html = "<div style='max-width: 300px; max-height: 400px; overflow-y: auto;'>"
    popup_html += "<h4 style='margin-bottom: 10px; color: #1f77b4;'>📋 Detail Feature</h4>"
    
    # Tambahkan semua kolom yang ada
    for col in row.index:
        if col != 'geometry' and pd.notna(row[col]) and row[col] != '':
            value = str(row[col])
            # Potong value yang terlalu panjang
            if len(value) > 100:
                value = value[:100] + "..."
            
            popup_html += f"""
            <div style='margin-bottom: 5px;'>
                <strong>{col}:</strong><br>
                <span style='word-wrap: break-word;'>{value}</span>
            </div>
            """
    
    popup_html += f"""
    <div style='margin-top: 10px; padding-top: 10px; border-top: 1px solid #ccc;'>
        <strong>Jarak:</strong> {row.get('jarak_meter', 'N/A'):.0f} meter<br>
        <strong>Tipe:</strong> {row.geometry.geom_type if hasattr(row, 'geometry') else 'N/A'}
    </div>
    </div>
    """
    return popup_html

# Fungsi untuk membuat peta interaktif
def create_interactive_map(gdf_nearby, gangguan_coords, zoom=15):
    """Membuat peta Folium dengan fitur klik interaktif"""
    # Tentukan lokasi awal peta
    if gangguan_coords:
        center_loc = gangguan_coords
    else:
        center_loc = [-6.2, 106.8]
    
    m = folium.Map(
        location=center_loc, 
        zoom_start=zoom, 
        control_scale=True
    )
    
    # Tambahkan event click handler
    m.add_child(folium.LatLngPopup())
    
    # Tambahkan instruksi klik
    folium.Marker(
        location=center_loc,
        icon=folium.DivIcon(
            html='<div style="background-color: white; padding: 5px; border: 1px solid #ccc; border-radius: 3px; font-size: 12px;">📍 Klik di peta untuk pilih lokasi gangguan</div>'
        )
    ).add_to(m)
    
    # Jika ada koordinat gangguan, tampilkan marker
    if gangguan_coords:
        # Tambahkan marker titik gangguan
        folium.Marker(
            location=gangguan_coords,
            popup=f"<b>🚨 TITIK GANGGUAN</b><br>Lat: {gangguan_coords[0]:.6f}<br>Lon: {gangguan_coords[1]:.6f}",
            icon=folium.Icon(color='red', icon='exclamation-triangle', prefix='fa')
        ).add_to(m)
        
        # Tambahkan buffer zone
        folium.Circle(
            location=gangguan_coords,
            radius=5000,  # 5km dalam meter
            color='red',
            fill=True,
            fillColor='red',
            fillOpacity=0.1,
            popup="Area Pencarian (5km)"
        ).add_to(m)
    
    # Tambahkan features terdekat jika ada
    if gdf_nearby is not None and not gdf_nearby.empty:
        for idx, row in gdf_nearby.iterrows():
            # Style berdasarkan tipe geometry
            if row.geometry.geom_type == 'Point':
                folium.Marker(
                    location=[row.geometry.y, row.geometry.x],
                    popup=folium.Popup(create_detailed_popup(row), max_width=400),
                    icon=folium.Icon(color='blue', icon='info-sign')
                ).add_to(m)
            
            elif row.geometry.geom_type in ['LineString', 'MultiLineString']:
                folium.GeoJson(
                    row.geometry.__geo_interface__,
                    style_function=lambda x: {
                        'color': 'green',
                        'weight': 4,
                        'opacity': 0.8
                    },
                    popup=folium.Popup(create_detailed_popup(row), max_width=400)
                ).add_to(m)
            
            elif row.geometry.geom_type in ['Polygon', 'MultiPolygon']:
                folium.GeoJson(
                    row.geometry.__geo_interface__,
                    style_function=lambda x: {
                        'fillColor': 'orange',
                        'color': 'orange',
                        'weight': 2,
                        'fillOpacity': 0.3
                    },
                    popup=folium.Popup(create_detailed_popup(row), max_width=400)
                ).add_to(m)
    
    return m

# Fungsi untuk analisis dari klik peta
def analyze_from_map_click(click_data, radius_km):
    """Melakukan analisis berdasarkan data klik dari peta"""
    if click_data and 'lat' in click_data and 'lng' in click_data:
        lat = click_data['lat']
        lng = click_data['lng']
        
        st.session_state.gangguan_coords = [lat, lng]
        st.session_state.analysis_done = True
        
        # Buat titik gangguan
        gangguan_point = Point(lng, lat)
        
        # Filter features terdekat
        with st.spinner(f"Mencari features dalam radius {radius_km} km..."):
            st.session_state.gdf_nearby = filter_features_nearby(
                st.session_state.gdf_master, 
                gangguan_point, 
                radius_km
            )
        
        return True
    return False

# UI Streamlit
st.title("🚨 GIS Quick Response - Analisis Gangguan")
st.markdown("**Pilih lokasi dengan klik peta atau input manual → Dapatkan info jaringan terdekat secara instan**")

# Sidebar untuk input
with st.sidebar:
    st.header("📍 Input Lokasi Gangguan")
    st.markdown("---")
    
    st.subheader("🎯 Cara 1: Klik di Peta")
    st.info("Klik langsung di peta untuk memilih lokasi gangguan")
    
    st.subheader("📝 Cara 2: Input Manual")
    # Input koordinat
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("Latitude", value=-6.200000, format="%.6f", step=0.000001, key="lat_input")
    with col2:
        lon = st.number_input("Longitude", value=106.816666, format="%.6f", step=0.000001, key="lon_input")
    
    # Radius pencarian
    radius_km = st.slider("Radius Pencarian (km)", 1, 20, 5, key="radius_input")
    
    # Tombol analisis
    col1, col2 = st.columns(2)
    with col1:
        analyze_btn = st.button("🚀 Analisis Gangguan", type="primary", use_container_width=True)
    with col2:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.analysis_done = False
            st.session_state.gdf_nearby = None
            st.session_state.gangguan_coords = None
            st.session_state.map_click_data = None
            st.session_state.last_click_coords = None
            st.rerun()
    
    st.markdown("---")
    st.header("⚙️ Settings")
    
    # Auto-zoom level
    zoom_level = st.slider("Zoom Level Peta", 10, 18, 15, key="zoom_input")
    
    st.markdown("---")
    st.info("""
    **Cara Penggunaan:**
    1. **Pilih lokasi** dengan klik di peta ATAU
    2. **Input koordinat** manual
    3. Atur radius pencarian
    4. Lihat hasil di peta & tabel
    """)

# Load master KML
if st.session_state.gdf_master is None:
    with st.spinner("Memuat data master KML... Mohon tunggu..."):
        st.session_state.gdf_master = load_master_kml()
        if st.session_state.gdf_master is not None:
            st.success(f"✅ Master KML loaded: {len(st.session_state.gdf_master)} features")

# Main content
if st.session_state.gdf_master is not None:
    # Buat peta interaktif
    st.header("🗺️ Peta Interaktif - Klik untuk Pilih Lokasi Gangguan")
    
    # Buat peta
    interactive_map = create_interactive_map(
        st.session_state.gdf_nearby, 
        st.session_state.gangguan_coords, 
        zoom_level
    )
    
    # Tampilkan peta dan capture klik
    map_data = st_folium(
        interactive_map, 
        width=1200, 
        height=500,
        key="interactive_map"
    )
    
    # Proses klik peta
    if map_data and map_data.get("last_clicked"):
        click_data = map_data["last_clicked"]
        # Cek jika klik baru berbeda dari yang sebelumnya
        current_click = (click_data['lat'], click_data['lng'])
        last_click = st.session_state.last_click_coords
        
        if last_click is None or abs(current_click[0] - last_click[0]) > 0.0001 or abs(current_click[1] - last_click[1]) > 0.0001:
            st.session_state.last_click_coords = current_click
            st.session_state.map_click_data = click_data
            
            # Otomatis lakukan analisis ketika peta diklik
            with st.spinner("Memproses lokasi yang dipilih..."):
                analyze_from_map_click(click_data, radius_km)
            st.rerun()
    
    # Jika tombol analisis manual ditekan
    if analyze_btn:
        st.session_state.analysis_done = True
        st.session_state.gangguan_coords = [lat, lon]
        
        # Buat titik gangguan
        gangguan_point = Point(lon, lat)
        
        # Filter features terdekat
        with st.spinner(f"Mencari features dalam radius {radius_km} km..."):
            st.session_state.gdf_nearby = filter_features_nearby(
                st.session_state.gdf_master, 
                gangguan_point, 
                radius_km
            )
        st.rerun()
    
    # Tampilkan informasi klik terbaru
    if st.session_state.map_click_data:
        st.info(f"📍 **Lokasi terpilih dari peta:** Lat: {st.session_state.map_click_data['lat']:.6f}, Lon: {st.session_state.map_click_data['lng']:.6f}")
    
    # Tampilkan hasil analisis jika sudah dilakukan
    if st.session_state.analysis_done and st.session_state.gangguan_coords:
        st.header(f"📊 Hasil Analisis Gangguan")
        
        # Tampilkan sumber lokasi
        if st.session_state.map_click_data:
            st.write(f"**Sumber:** Klik Peta | **Lokasi:** {st.session_state.gangguan_coords[0]:.6f}, {st.session_state.gangguan_coords[1]:.6f}")
        else:
            st.write(f"**Sumber:** Input Manual | **Lokasi:** {st.session_state.gangguan_coords[0]:.6f}, {st.session_state.gangguan_coords[1]:.6f}")
        
        st.write(f"**Radius:** {radius_km} km")
        
        # Tampilkan statistik
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Features Ditemukan", 
                     len(st.session_state.gdf_nearby) if st.session_state.gdf_nearby is not None else 0)
        
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
        
        # Tampilkan tabel hasil
        if st.session_state.gdf_nearby is not None and not st.session_state.gdf_nearby.empty:
            st.header("📋 Detail Features Terdekat")
            
            # Siapkan data untuk tabel
            display_df = st.session_state.gdf_nearby.copy()
            
            # Pilih kolom yang ingin ditampilkan (exclude geometry)
            cols_to_display = [col for col in display_df.columns if col != 'geometry']
            
            # Buat tabel dengan kolom yang relevan
            if 'name' in display_df.columns:
                display_columns = ['name', 'jarak_meter'] + [col for col in cols_to_display if col not in ['name', 'jarak_meter']]
            else:
                display_columns = ['jarak_meter'] + [col for col in cols_to_display if col != 'jarak_meter']
            
            # Tampilkan dataframe
            st.dataframe(
                display_df[display_columns],
                use_container_width=True,
                column_config={
                    "name": "Nama Feature",
                    "jarak_meter": st.column_config.NumberColumn(
                        "Jarak (meter)",
                        format="%.0f m"
                    )
                }
            )
            
            # Download hasil
            csv_data = display_df[display_columns].to_csv(index=False)
            st.download_button(
                label="📥 Download Hasil Analisis (CSV)",
                data=csv_data,
                file_name=f"gangguan_{st.session_state.gangguan_coords[0]:.6f}_{st.session_state.gangguan_coords[1]:.6f}_{datetime.now().strftime('%H%M')}.csv",
                mime="text/csv",
                key="download_btn"
            )
        else:
            st.warning("⚠️ Tidak ada features ditemukan dalam radius yang ditentukan. Coba perbesar radius pencarian.")
    
    else:
        # Tampilan awal sebelum analisis
        st.markdown("""
        ## 🚀 Sistem Quick Response Gangguan
        
        **Fitur Unggulan:**
        - 🖱️ **Klik Peta** - Pilih lokasi gangguan langsung dari peta
        - ⚡ **Super Cepat** - Filter lokal tanpa load ulang data besar
        - 📍 **Input Manual** - Alternatif input koordinat manual
        - 🎯 **Filter Cerdas** - Hanya tampilkan features terdekat
        - 📊 **Info Lengkap** - Semua atribut KML tersedia
        
        **Statistik Data Master:**
        """)
        
        # Tampilkan info data master
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Features", len(st.session_state.gdf_master))
        
        with col2:
            geometry_types = st.session_state.gdf_master.geometry.type.unique()
            st.metric("Jenis Geometri", len(geometry_types))
        
        with col3:
            if 'name' in st.session_state.gdf_master.columns:
                named_features = st.session_state.gdf_master['name'].notna().sum()
                st.metric("Features Bernama", named_features)
            else:
                st.metric("Kolom Tersedia", len(st.session_state.gdf_master.columns))

else:
    st.error("""
    ❌ File master KML tidak dapat dimuat.
    
    **Solusi:**
    1. Pastikan file `zxcmcnc.kml` ada di folder yang sama dengan aplikasi
    2. Cek path file di variabel `KML_MASTER_PATH`
    3. Pastikan format KML valid
    """)

# Footer
st.markdown("---")
st.markdown(
    "**GIS Quick Response** © 2024 | Fitur Klik Peta Aktif | Response Time: < 3s"
)
