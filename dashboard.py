import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import json
import os
from datetime import date, datetime
import requests
import time

# ----------------------------
# Page Config
# ----------------------------
st.set_page_config(
    page_title="EchoBand Emergency Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ----------------------------
# Initialize Directories
# ----------------------------
SAVE_DIR = "saved_tracks"
os.makedirs(SAVE_DIR, exist_ok=True)

# ----------------------------
# Session State Initialization
# ----------------------------
if "tracking" not in st.session_state:
    st.session_state.tracking = False

if "path" not in st.session_state:
    st.session_state.path = []

if "full_route" not in st.session_state:
    st.session_state.full_route = []

if "current_index" not in st.session_state:
    st.session_state.current_index = 0

if "show_live_tracking" not in st.session_state:
    st.session_state.show_live_tracking = False

if "selected_replay" not in st.session_state:
    st.session_state.selected_replay = None

if "replay_index" not in st.session_state:
    st.session_state.replay_index = 0

if "replaying" not in st.session_state:
    st.session_state.replaying = False

# ----------------------------
# Helper Functions
# ----------------------------
def get_route_from_osrm(start_lat, start_lon, end_lat, end_lon):
    """Get detailed route using OSRM (Open Source Routing Machine)"""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=geojson"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data['code'] == 'Ok':
            coordinates = data['routes'][0]['geometry']['coordinates']
            # Convert [lon, lat] to [lat, lon]
            route = [[coord[1], coord[0]] for coord in coordinates]
            return route
        else:
            # Fallback to straight line
            return [[start_lat, start_lon], [end_lat, end_lon]]
    except Exception as e:
        st.error(f"Error getting route: {e}")
        # Fallback to straight line if API fails
        return [[start_lat, start_lon], [end_lat, end_lon]]

def create_live_map(path, full_route, current_index):
    """Create the live tracking map"""
    if path:
        center = path[-1]
    else:
        center = [19.0760, 72.8777]
    
    m = folium.Map(
        location=center,
        zoom_start=15,
        tiles="OpenStreetMap"
    )
    
    # Custom icon (with fallback)
    try:
        icon = folium.CustomIcon(
            icon_image="girl.jpg",
            icon_size=(40, 40)
        )
    except:
        icon = folium.Icon(color="red", icon="user")
    
    # Draw tracking if active
    if path:
        # Start marker
        folium.Marker(
            location=path[0],
            popup="🏁 Start Point",
            icon=folium.Icon(color="green", icon="play")
        ).add_to(m)
        
        # Current position (moving marker)
        folium.Marker(
            location=path[-1],
            popup="📍 Current Location",
            icon=icon
        ).add_to(m)
        
        # Draw path traveled so far
        folium.PolyLine(
            path,
            color="purple",
            weight=6,
            opacity=0.8
        ).add_to(m)
        
        # If tracking, show remaining route in lighter color
        if full_route and current_index < len(full_route):
            remaining_route = full_route[current_index:]
            if remaining_route:
                folium.PolyLine(
                    remaining_route,
                    color="lightblue",
                    weight=3,
                    opacity=0.4,
                    dash_array="10"
                ).add_to(m)
                
                # End marker
                folium.Marker(
                    location=full_route[-1],
                    popup="🎯 Destination",
                    icon=folium.Icon(color="red", icon="stop")
                ).add_to(m)
    
    return m

def create_replay_map(full_path, replay_index):
    """Create the replay map"""
    display_path = full_path[:replay_index + 1]
    
    m = folium.Map(
        location=display_path[-1],
        zoom_start=15,
        tiles="OpenStreetMap"
    )
    
    try:
        icon = folium.CustomIcon(
            icon_image="girl.jpg",
            icon_size=(40, 40)
        )
    except:
        icon = folium.Icon(color="red", icon="user")
    
    # Draw traveled path
    if len(display_path) > 1:
        folium.PolyLine(
            display_path,
            color="purple",
            weight=6,
            opacity=0.8
        ).add_to(m)
    
    # Remaining path (faded)
    if replay_index < len(full_path) - 1:
        remaining = full_path[replay_index:]
        folium.PolyLine(
            remaining,
            color="lightgray",
            weight=3,
            opacity=0.4,
            dash_array="10"
        ).add_to(m)
    
    # Start marker
    folium.Marker(
        full_path[0],
        popup="🏁 Start",
        icon=folium.Icon(color="green", icon="play")
    ).add_to(m)
    
    # Current position
    folium.Marker(
        display_path[-1],
        popup="📍 Current Position",
        icon=icon
    ).add_to(m)
    
    # End marker
    folium.Marker(
        full_path[-1],
        popup="🎯 Destination",
        icon=folium.Icon(color="red", icon="stop")
    ).add_to(m)
    
    return m

def create_static_map(lat, lon):
    """Create a static map for last known location"""
    m = folium.Map(location=[lat, lon], zoom_start=15)
    
    try:
        icon = folium.CustomIcon(
            icon_image="girl.jpg",
            icon_size=(40, 40)
        )
    except:
        icon = folium.Icon(color="red", icon="info-sign")
    
    folium.Marker(
        [lat, lon],
        popup="Last Known Location",
        tooltip="EchoBand User",
        icon=icon
    ).add_to(m)
    
    return m

def generate_gps_route(start_lat, start_lon, end_lat, end_lon, num_points=50):
    """Generate a smooth GPS route between two points with many intermediate waypoints"""
    route = []
    for i in range(num_points):
        progress = i / (num_points - 1)
        # Add some randomness to make it look more realistic
        lat = start_lat + (end_lat - start_lat) * progress + (0.0001 * (i % 3 - 1))
        lon = start_lon + (end_lon - start_lon) * progress + (0.0001 * ((i + 1) % 3 - 1))
        route.append([lat, lon])
    return route

# ----------------------------
# Custom CSS
# ----------------------------
st.markdown("""
    <style>
    .stButton button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1rem;
        transition: all 0.3s;
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    div[data-testid="stDataFrame"] {
        border-radius: 8px;
        overflow: hidden;
    }
    
    .tracking-controls {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1rem;
    }
    
    .tracking-controls h3 {
        color: white;
        margin-top: 0;
    }
    </style>
""", unsafe_allow_html=True)

# ----------------------------
# Header
# ----------------------------
st.markdown(
    """
    <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
                padding: 1.5rem; 
                text-align: center; 
                border-radius: 12px;
                margin-bottom: 2rem;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h1 style="color: white; margin: 0; font-size: 2.5rem;">
            🛡️ EchoBand Emergency Dashboard
        </h1>
        <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0; font-size: 1.1rem;">
            Real-time Monitoring & Location Tracking System
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

# ----------------------------
# Main Layout
# ----------------------------
left_col, right_col = st.columns([2, 1])

# ----------------------------
# LEFT COLUMN
# ----------------------------
with left_col:
    # Device Status
    st.markdown("### 📱 Device Status")
    
    band_active = st.session_state.tracking or st.session_state.selected_replay is not None
    
    status_color = "#dc2626" if band_active else "#16a34a"
    status_text = "ACTIVE – Emergency Mode" if band_active else "INACTIVE – Normal Mode"
    
    st.markdown(
        f"""
        <div style="background-color: {status_color}; 
                    padding: 1.5rem; 
                    border-radius: 10px; 
                    text-align: center; 
                    font-size: 1.3rem; 
                    font-weight: bold; 
                    color: white;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    margin-bottom: 1.5rem;">
            {status_text}
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Incident Log
    st.markdown("### 📋 Incident Log")
    
    # Incident data with GPS coordinates stored separately
    incident_data = {
        "Date & Time": [
            "2025-09-15 18:32", "2025-09-14 22:11", "2025-09-12 21:00",
            "2025-09-10 17:45", "2025-09-07 20:10", "2025-09-05 19:30"
        ],
        "Trigger Type": ["Button Pressed"] * 6,
        "Peak BPM": [138, 125, 142, 98, 135, 122],
        "Duration (s)": [45, 30, 60, 20, 50, 25],
        "Status": ["Acknowledged", "Escalated", "Acknowledged", "Auto-cleared", "Escalated", "Acknowledged"],
        "Acknowledged By": ["Mom", "—", "Dad", "—", "Best Friend", "Mom"],
        "Remarks": [
            "False alarm ruled out", "Needs follow-up", "Situation resolved",
            "False trigger", "Contacted local police", "Panic attack (medical)"
        ],
        "GPS_Coords": [
            generate_gps_route(19.1176, 72.9060, 19.1210, 72.9090, 50),
            generate_gps_route(19.1120, 72.9081, 19.1150, 72.9110, 45),
            generate_gps_route(19.1200, 72.9099, 19.1230, 72.9130, 55),
            generate_gps_route(19.1190, 72.9075, 19.1220, 72.9105, 40),
            generate_gps_route(19.1150, 72.9055, 19.1180, 72.9085, 60),
            generate_gps_route(19.1165, 72.9020, 19.1195, 72.9050, 48)
        ],
        "Filename": [
            "2025-09-15_18-32.json", "2025-09-14_22-11.json", "2025-09-12_21-00.json",
            "2025-09-10_17-45.json", "2025-09-07_20-10.json", "2025-09-05_19-30.json"
        ]
    }
    
    # Save GPS data for each incident
    for i, filename in enumerate(incident_data["Filename"]):
        filepath = os.path.join(SAVE_DIR, filename)
        if not os.path.exists(filepath):
            with open(filepath, "w") as f:
                json.dump(incident_data["GPS_Coords"][i], f)
    
    # Display table without GPS_Coords and Filename columns
    display_df = pd.DataFrame({
        "Date & Time": incident_data["Date & Time"],
        "Trigger Type": incident_data["Trigger Type"],
        "Peak BPM": incident_data["Peak BPM"],
        "Duration (s)": incident_data["Duration (s)"],
        "Status": incident_data["Status"],
        "Acknowledged By": incident_data["Acknowledged By"],
        "Remarks": incident_data["Remarks"]
    })
    
    st.dataframe(display_df, use_container_width=True, height=250)
    
    # See More buttons for GPS replay
    st.markdown("#### 🗺️ View GPS Tracking History")
    
    # Get all saved track files
    saved_files = sorted([f for f in os.listdir(SAVE_DIR) if f.endswith('.json')], reverse=True)
    
    if not saved_files:
        st.info("No tracking data saved yet. Start live tracking and click 'Stop' to save.")
    else:
        # Display saved tracks in grid format
        num_cols = 3
        cols = st.columns(num_cols)
        
        for i, filename in enumerate(saved_files):
            col_idx = i % num_cols
            col = cols[col_idx]
            
            # Format the display name from filename
            # Convert "2025-01-27_14-30.json" to "2025-01-27 14:30"
            display_name = filename.replace('.json', '').replace('_', ' ')
            
            if col.button(f"📍 {display_name}", key=f"replay_{filename}"):
                st.session_state.selected_replay = filename
                st.session_state.replay_index = 0
                st.session_state.replaying = False
                st.session_state.show_live_tracking = False
                st.rerun()

# ----------------------------
# RIGHT COLUMN
# ----------------------------
with right_col:
    # Choose between Live Tracking, Replay, or Static Map
    if st.session_state.show_live_tracking or st.session_state.tracking:
        st.markdown("### 🛰️ Live Location Tracking (Simulation)")
        
        # Live Tracking Controls
        with st.container():
            st.markdown('<div class="tracking-controls">', unsafe_allow_html=True)
            st.markdown("#### Control Panel")
            
            today = st.date_input("Tracking Date", date.today(), key="live_date")
            
            col1, col2 = st.columns(2)
            start_lat = col1.number_input("Start Lat", value=19.0760, format="%.6f", key="start_lat")
            start_lon = col2.number_input("Start Lon", value=72.8777, format="%.6f", key="start_lon")
            
            col3, col4 = st.columns(2)
            end_lat = col3.number_input("End Lat", value=19.0896, format="%.6f", key="end_lat")
            end_lon = col4.number_input("End Lon", value=72.8656, format="%.6f", key="end_lon")
            
            speed = st.slider("Tracking Speed", min_value=1, max_value=20, value=5, key="live_speed")
            
            col_start, col_stop, col_reset = st.columns(3)
            
            start_btn = col_start.button("▶ Start", use_container_width=True)
            stop_btn = col_stop.button("⏹ Stop", use_container_width=True)
            reset_btn = col_reset.button("🔄 Reset", use_container_width=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Handle button actions
        if start_btn:
            with st.spinner("🗺️ Getting route..."):
                route = get_route_from_osrm(start_lat, start_lon, end_lat, end_lon)
            
            st.session_state.tracking = True
            st.session_state.full_route = route
            st.session_state.path = [route[0]]
            st.session_state.current_index = 0
            st.success(f"✅ Route loaded with {len(route)} waypoints!")
        
        if stop_btn and st.session_state.path:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            save_path = os.path.join(SAVE_DIR, f"{timestamp}.json")
            
            with open(save_path, "w") as f:
                json.dump(st.session_state.path, f)
            
            st.success(f"✅ Saved GPS track: {timestamp}")
            st.session_state.tracking = False
            
            # Reset tracking state
            st.session_state.path = []
            st.session_state.full_route = []
            st.session_state.current_index = 0
            st.session_state.show_live_tracking = False
            
            # Force rerun to show updated history
            time.sleep(1)
            st.rerun()
        
        if reset_btn:
            st.session_state.tracking = False
            st.session_state.path = []
            st.session_state.full_route = []
            st.session_state.current_index = 0
            st.session_state.show_live_tracking = False
            st.rerun()
        
        # Progress bar
        if st.session_state.full_route:
            progress = len(st.session_state.path) / len(st.session_state.full_route)
            st.progress(progress, text=f"Progress: {int(progress * 100)}%")
            
            # Show current location
            if st.session_state.path:
                current_pos = st.session_state.path[-1]
                st.info(f"📍 **Current Location:** {current_pos[0]:.6f}, {current_pos[1]:.6f}")
        
        # Display live map
        map_placeholder = st.empty()
        m = create_live_map(st.session_state.path, st.session_state.full_route, st.session_state.current_index)
        with map_placeholder.container():
            st_folium(m, height=500, width="100%", returned_objects=[])
        
        # Auto-update logic
        if st.session_state.tracking and st.session_state.full_route:
            if st.session_state.current_index < len(st.session_state.full_route) - 1:
                # Add next waypoint(s) based on speed
                for _ in range(speed):
                    st.session_state.current_index += 1
                    if st.session_state.current_index < len(st.session_state.full_route):
                        st.session_state.path.append(st.session_state.full_route[st.session_state.current_index])
                    else:
                        break
                
                # Auto-rerun to continue tracking
                time.sleep(0.3)
                st.rerun()
            else:
                st.session_state.tracking = False
                # Show final location instead of balloons
                final_pos = st.session_state.full_route[-1]
                st.success(f"🎯 Current Location: {final_pos[0]:.6f}, {final_pos[1]:.6f}")
    
    elif st.session_state.selected_replay:
        st.markdown("### 🎬 GPS Replay")
        
        # Replay Controls
        file_path = os.path.join(SAVE_DIR, st.session_state.selected_replay)
        
        if os.path.exists(file_path):
            with open(file_path) as f:
                full_path = json.load(f)
            
            col1, col2, col3, col4 = st.columns(4)
            
            if col1.button("▶ Play", key="replay_play"):
                st.session_state.replaying = True
                if st.session_state.replay_index >= len(full_path) - 1:
                    st.session_state.replay_index = 0
            
            if col2.button("⏸ Pause", key="replay_pause"):
                st.session_state.replaying = False
            
            if col3.button("🔄 Reset", key="replay_reset"):
                st.session_state.replay_index = 0
                st.session_state.replaying = False
                st.rerun()
            
            if col4.button("❌ Close", key="replay_close"):
                st.session_state.selected_replay = None
                st.session_state.replaying = False
                st.session_state.replay_index = 0
                st.rerun()
            
            replay_speed = st.slider("Replay Speed", min_value=1, max_value=30, value=10, key="replay_speed")
            
            # Progress
            progress = (st.session_state.replay_index + 1) / len(full_path) if full_path else 0
            st.progress(progress, text=f"Progress: {int(progress * 100)}%")
            
            # Show current location in replay
            current_pos = full_path[st.session_state.replay_index]
            st.info(f"📍 **Replay Position:** {current_pos[0]:.6f}, {current_pos[1]:.6f}")
            
            # Create and display replay map
            map_placeholder = st.empty()
            m = create_replay_map(full_path, st.session_state.replay_index)
            with map_placeholder.container():
                st_folium(m, height=500, width="100%", returned_objects=[])
            
            # Auto-replay logic
            if st.session_state.replaying:
                if st.session_state.replay_index < len(full_path) - 1:
                    for _ in range(replay_speed):
                        st.session_state.replay_index += 1
                        if st.session_state.replay_index >= len(full_path) - 1:
                            st.session_state.replaying = False
                            break
                    
                    time.sleep(0.3)
                    st.rerun()
                else:
                    st.session_state.replaying = False
                    # Show final location
                    final_pos = full_path[-1]
                    st.success(f"✅ Replay completed at: {final_pos[0]:.6f}, {final_pos[1]:.6f}")
    
    else:
        # Static last known location map
        st.markdown("### 📍 Last Known Location")
        
        # Button to start live tracking
        if st.button("🛰️ Start Live Tracking", use_container_width=True):
            st.session_state.show_live_tracking = True
            st.rerun()
        
        latitude, longitude = 19.1176, 72.9060
        
        st.info(f"**Coordinates:** {latitude:.6f}, {longitude:.6f}")
        
        m = create_static_map(latitude, longitude)
        st_folium(m, height=500, width="100%", returned_objects=[])

# ----------------------------
# Emergency Contacts Section
# ----------------------------
st.markdown("---")
st.markdown("### 🚨 Emergency Contacts")

contacts = {
    "Name": ["Mom", "Dad", "Best Friend", "Local Police"],
    "Phone": ["+91-9876543210", "+91-9123456780", "+91-9988776655", "100"],
    "Relation": ["Primary Contact", "Secondary Contact", "Friend", "Authority"],
    "Status": ["Active", "Active", "Active", "Available"]
}
df_contacts = pd.DataFrame(contacts)

st.table(df_contacts)