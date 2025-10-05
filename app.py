# Add these imports at the top
import requests
import json
from urllib.parse import urlparse

# 1. Add error handling and validation
def validate_coordinates(lat, lon):
    """Validate coordinate ranges"""
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        raise ValueError("Coordinates out of valid range")
    return True

# 2. Add caching for better performance
@st.cache_data(show_spinner=False, ttl=3600)
def load_kml_cached(file_path):
    """Cached version of KML loading"""
    return load_kml_comprehensive(file_path)

# 3. Add more basemap options
BASEMAP_OPTIONS = {
    "OpenStreetMap": "OpenStreetMap",
    "Stamen Terrain": "Stamen Terrain", 
    "Stamen Toner": "Stamen Toner",
    "Satellite (Esri)": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "CartoDB Dark": "CartoDB dark_matter",
    "CartoDB Light": "CartoDB positron"
}

# 4. Add coordinate conversion utilities
def convert_dms_to_decimal(degrees, minutes, seconds, direction):
    """Convert DMS to decimal degrees"""
    decimal = degrees + minutes/60 + seconds/3600
    if direction in ['S', 'W']:
        decimal = -decimal
    return decimal

# 5. Add export in multiple formats
def export_data(gdf, format_type='csv'):
    """Export data in multiple formats"""
    if format_type == 'csv':
        return gdf.to_csv(index=False)
    elif format_type == 'geojson':
        return gdf.to_json()
    elif format_type == 'kml':
        # Simple KML export implementation
        return convert_to_kml(gdf)
    return None

# 6. Add measurement tools
def calculate_area(geometry):
    """Calculate area in hectares"""
    try:
        # Convert to UTM for accurate area calculation
        utm_crs = gdf.estimate_utm_crs()
        return geometry.to_crs(utm_crs).area / 10000
    except:
        return None

# 7. Add batch processing capability
def batch_analysis(coordinates_list, radius_km=5):
    """Process multiple locations at once"""
    results = []
    for coords in coordinates_list:
        point = Point(coords[1], coords[0])  # lon, lat
        nearby = filter_features_nearby(st.session_state.gdf_master, point, radius_km)
        results.append({
            'coordinates': coords,
            'features_found': len(nearby),
            'closest_distance': nearby['jarak_meter'].min() if not nearby.empty else None
        })
    return pd.DataFrame(results)

# 8. Enhanced popup with more details
def create_enhanced_popup(row):
    """Create more informative popups"""
    popup_html = "<div style='max-width: 400px; max-height: 500px; overflow-y: auto;'>"
    
    # Add geometry-specific info
    geom = row.geometry
    if geom.geom_type == 'Polygon':
        area_ha = calculate_area(geom)
        popup_html += f"<div><strong>Area:</strong> {area_ha:.2f} ha</div>"
    elif geom.geom_type == 'LineString':
        length_km = geom.length * 111  # Approximate km
        popup_html += f"<div><strong>Length:</strong> {length_km:.2f} km</div>"
    
    # Add existing details
    popup_html += create_detailed_popup(row)
    return popup_html

# 9. Add data quality indicators
def calculate_data_quality(gdf):
    """Calculate data quality metrics"""
    total_features = len(gdf)
    valid_geometry = gdf.geometry.is_valid.sum()
    has_name = gdf['name'].notna().sum() if 'name' in gdf.columns else 0
    
    return {
        'total_features': total_features,
        'valid_geometry_percent': (valid_geometry / total_features) * 100,
        'named_features_percent': (has_name / total_features) * 100 if 'name' in gdf.columns else 0
    }

# Update the UI section with new features
def add_advanced_controls():
    """Add advanced controls to sidebar"""
    with st.sidebar.expander("🛠️ Advanced Options"):
        # Coordinate converter
        st.subheader("Coordinate Converter")
        col1, col2 = st.columns(2)
        with col1:
            dms_lat = st.number_input("Lat Degrees", value=6)
            dms_lat_min = st.number_input("Lat Minutes", value=12)
            dms_lat_sec = st.number_input("Lat Seconds", value=34.56)
            lat_dir = st.selectbox("Lat Direction", ["N", "S"])
        with col2:
            dms_lon = st.number_input("Lon Degrees", value=106)
            dms_lon_min = st.number_input("Lon Minutes", value=49)
            dms_lon_sec = st.number_input("Lon Seconds", value=0.0)
            lon_dir = st.selectbox("Lon Direction", ["E", "W"])
        
        if st.button("Convert to Decimal"):
            decimal_lat = convert_dms_to_decimal(dms_lat, dms_lat_min, dms_lat_sec, lat_dir)
            decimal_lon = convert_dms_to_decimal(dms_lon, dms_lon_min, dms_lon_sec, lon_dir)
            st.session_state.lat_input = decimal_lat
            st.session_state.lon_input = decimal_lon
            st.success(f"Converted: {decimal_lat:.6f}, {decimal_lon:.6f}")
        
        # Batch analysis
        st.subheader("Batch Analysis")
        uploaded_file = st.file_uploader("Upload coordinates CSV", type=['csv'])
        if uploaded_file:
            coords_df = pd.read_csv(uploaded_file)
            if st.button("Process Batch"):
                with st.spinner("Processing batch..."):
                    results = batch_analysis(coords_df.values)
                    st.dataframe(results)
                    
                    # Download batch results
                    csv_results = results.to_csv(index=False)
                    st.download_button(
                        "📥 Download Batch Results",
                        csv_results,
                        "batch_analysis_results.csv"
                    )

# Update the main function calls
def main():
    # Add advanced controls
    add_advanced_controls()
    
    # Use cached loading
    if st.session_state.gdf_master is None:
        with st.spinner("🔄 MEMUAT DATA KML... Ini mungkin butuh beberapa detik..."):
            st.session_state.gdf_master = load_kml_cached(KML_MASTER_PATH)
    
    # Add data quality info
    if st.session_state.gdf_master is not None:
        quality = calculate_data_quality(st.session_state.gdf_master)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Data Quality Score", f"{quality['valid_geometry_percent']:.1f}%")
        with col2:
            st.metric("Named Features", f"{quality['named_features_percent']:.1f}%")
        with col3:
            st.metric("Total Features", quality['total_features'])

# Call the updated main function
if __name__ == "__main__":
    main()
