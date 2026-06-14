import streamlit as st
from PIL import Image
from rembg import remove
import io
import json
from google import genai

# Initialize Gemini Client (Expects GEMINI_API_KEY environment variable)
try:
    client = genai.Client()
except Exception:
    client = None

# --- BASIC APP CONFIG (NEUTRAL STYLE) ---
st.set_page_config(page_title="Shared Virtual Closet", layout="wide")

st.title("🪞 Shared Virtual Dressing Room")
st.write("Welcome to your shared closet app. Use the sidebar to upload profiles and clothing.")

# --- SESSION STATE INITIALIZATION ---
if "profiles" not in st.session_state:
    st.session_state.profiles = {
        "Sarah's Closet": {"avatar": None, "closet": {"Tops": [], "Bottoms": [], "Accessories": []}},
        "Mark's Closet": {"avatar": None, "closet": {"Tops": [], "Bottoms": [], "Accessories": []}}
    }
if "history" not in st.session_state:
    st.session_state.history = {"liked_combos": [], "disliked_combos": []}

# --- AI TAGGING PIPELINE ---
def process_clothing_image(uploaded_file):
    """Removes backgrounds cleanly for accurate layer fitting."""
    input_bytes = uploaded_file.read()
    output_bytes = remove(input_bytes)
    return Image.open(io.BytesIO(output_bytes))

def ai_generate_clothing_tags(image, category):
    """Generates specific tags matching your parameters (Weather, Season, Occasion)."""
    if not client:
        return ["Casual", "Spring", "Mall"]
        
    prompt = f"""
    Analyze this '{category}' item. Provide context tags across 4 categories:
    1. Weather (e.g., Hot, Cold, Rainy, Mild)
    2. Season (e.g., Summer, Fall, Winter, Spring)
    3. Occasions (List all that apply: Work, Mall, Wedding, BBQ, Date Night, Casual, Formal)
    4. General Style/Color notes.
    Return strictly as a flat JSON list of strings, like: ["Cold", "Winter", "Work", "Formal", "Black", "Wool"]
    """
    try:
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, img_bytes]
        )
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_text)
    except Exception:
        return ["Casual", "Summer", "BBQ"]

# --- SIDEBAR: PROFILES & UPLOADS ---
with st.sidebar:
    st.header("👤 Account Setup")
    
    # Active Profile Selection
    current_user = st.radio("Who is using the closet right now?", ["Sarah's Closet", "Mark's Closet"])
    other_user = "Mark's Closet" if current_user == "Sarah's Closet" else "Sarah's Closet"
    
    # Profile Body Avatar Upload
    avatar_file = st.file_uploader("Upload standing full-body photo:", type=["png", "jpg", "jpeg"])
    if avatar_file:
        st.session_state.profiles[current_user]["avatar"] = Image.open(avatar_file)
        st.success("Avatar saved successfully!")

    st.write("---")
    st.header("➕ Add New Clothes")
    
    upload_target = st.selectbox("Add item to whose closet?", [current_user, other_user])
    cat = st.selectbox("Item Category", ["Tops", "Bottoms", "Accessories"])
    item_file = st.file_uploader("Choose clothing image:", type=["png", "jpg", "jpeg"])
    
    custom_tags_input = st.text_input("Extra custom tags (comma-separated):", placeholder="vintage, oversized")

    if st.button("✨ Scan & Save to Closet") and item_file:
        with st.spinner("Isolating clothing item..."):
            processed_img = process_clothing_image(item_file)
        with st.spinner("AI analyzing tags for seasons & events..."):
            ai_tags = ai_generate_clothing_tags(processed_img, cat)
        
        if custom_tags_input:
            custom_tags = [t.strip() for t in custom_tags_input.split(",") if t.strip()]
            ai_tags.extend(custom_tags)
            
        final_tags = list(set(ai_tags))
        
        item_data = {"image": processed_img, "tags": final_tags}
        st.session_state.profiles[upload_target]["closet"][cat].append(item_data)
        st.success(f"Successfully added to {upload_target}!")

# --- MAIN APP INTERFACE: FILTERING & MIX & MATCH ---
st.subheader(f"Current Dressing Room: {current_user}")

# Access Toggles (Borrowing Clothes Feature)
borrow_clothes = st.checkbox(f"🔄 Cross-reference and borrow clothing layers from {other_user}", value=False)
source_profile = st.session_state.profiles[current_user]

# --- GLOBAL FILTERS ---
st.write("### 🔍 Filter Options")
f_col1, f_col2, f_col3 = st.columns(3)

with f_col1:
    weather_filter = st.selectbox("Current Weather", ["All Weather", "Hot", "Cold", "Mild", "Rainy"])
with f_col2:
    season_filter = st.selectbox("Current Season", ["All Seasons", "Summer", "Winter", "Spring", "Fall"])
with f_col3:
    occasion_filter = st.selectbox("Target Occasion", ["All Occasions", "Work", "Mall", "Wedding", "BBQ", "Date Night", "Casual"])

# Filtering logic helper function
def get_filtered_pool(category):
    pool = []
    for i, item in enumerate(st.session_state.profiles[current_user]["closet"][category]):
        pool.append({"item": item, "source": current_user, "index": i})
    
    if borrow_clothes:
        for i, item in enumerate(st.session_state.profiles[other_user]["closet"][category]):
            pool.append({"item": item, "source": other_user, "index": i})
            
    filtered_pool = []
    for entry in pool:
        tags = [t.lower() for t in entry["item"]["tags"]]
        if weather_filter != "All Weather" and weather_filter.lower() not in tags:
            continue
        if season_filter != "All Seasons" and season_filter.lower() not in tags:
            continue
        if occasion_filter != "All Occasions" and occasion_filter.lower() not in tags:
            continue
        filtered_pool.append(entry)
    return filtered_pool

tops_pool = get_filtered_pool("Tops")
bottoms_pool = get_filtered_pool("Bottoms")
acc_pool = get_filtered_pool("Accessories")

# --- APP LAYOUT ---
view_col1, view_col2 = st.columns([5, 5])

with view_col1:
    st.write("### 👤 Silhouette Alignment")
    if source_profile["avatar"]:
        st.image(source_profile["avatar"], caption="Your Standing Fitting Silhouette", use_container_width=True)
    else:
        st.info("Upload your standing full-body photo in the sidebar to sync your virtual silhouette layout here.")

with view_col2:
    st.write("### 🔄 Mix & Match Carousel")
    
    if len(tops_pool) > 0 and len(bottoms_pool) > 0:
        top_sel = st.select_slider("Cycle Tops", options=range(len(tops_pool)), format_func=lambda x: f"Top {x+1} ({tops_pool[x]['source']})")
        bottom_sel = st.select_slider("Cycle Bottoms", options=range(len(bottoms_pool)), format_func=lambda x: f"Bottom {x+1} ({bottoms_pool[x]['source']})")
        
        active_top = tops_pool[top_sel]["item"]
        active_bottom = bottoms_pool[bottom_sel]["item"]
        
        outfit_display = st.columns(2)
        with outfit_display[0]:
            st.image(active_top["image"], caption="Selected Top", use_container_width=True)
            st.write(f"Tags: {', '.join(active_top['tags'])}")
            
        with outfit_display[1]:
            st.image(active_bottom["image"], caption="Selected Bottom", use_container_width=True)
            st.write(f"Tags: {', '.join(active_top['tags'])}")
