TextEdit
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

# --- APP CONFIG & CUSTOM RETRO FUNKY STYLING ---
st.set_page_config(page_title="Shared Virtual Closet", layout="wide")

# Custom CSS injecting the precise retro green/pink palette and "Young Serif" font family
st.markdown("""
    <style>
    /* Import your custom heavy, curvy retro vintage serif fonts from Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Young+Serif&family=DM+Serif+Display&family=Inter:wght@400;600&display=swap');
    
    /* Global Background and Global Font transpositions */
    html, body, [class*="css"], .stApp {
        background-color: #2D6A4F !important; /* Rich Sage/Grid Green Base Color */
        color: #FFFFFF !important;
        font-family: 'Young Serif', serif !important;
    }
    
    /* Transpose the custom curvy font onto ALL specific app headers, labels and titles */
    h1, h2, h3, h4, h5, h6, .profile-header, label, .stRadio label, p {
        font-family: 'Young Serif', serif !important;
        font-weight: normal !important;
        color: #FF8FAB !important; /* Funky Vintage Pink text accent color */
        letter-spacing: 0.5px;
    }
    
    /* App Dashboard Enclosure wrapper mimicking a structured desktop panel */
    .main-panel {
        background-color: #F8F6F0 !important; /* Clean retro off-white paper color */
        border: 3px solid #1A1A1A;
        border-radius: 16px;
        padding: 25px;
        box-shadow: 8px 8px 0px #1A1A1A; /* Crisp block shadow */
        color: #1A1A1A !important;
    }
    
    /* Style all text inside buttons and selectboxes to carry your custom font */
    div.stButton > button {
        font-family: 'Young Serif', serif !important;
        background-color: #FF8FAB !important; /* Pink Background */
        color: #1A1A1A !important;
        border: 2px solid #1A1A1A !important;
        border-radius: 8px !important;
        box-shadow: 3px 3px 0px #1A1A1A !important;
        transition: all 0.2s;
    }
    
    div.stButton > button:hover {
        transform: translate(-1px, -1px);
        box-shadow: 4px 4px 0px #1A1A1A !important;
        background-color: #FFA5AB !important;
    }
    
    /* Customized visual badge tags for clothing parameters */
    .tag-badge {
        display: inline-block;
        background-color: #FF8FAB;
        color: #1A1A1A;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 11px;
        padding: 4px 10px;
        border-radius: 20px;
        margin-right: 5px;
        margin-top: 5px;
        border: 1px solid #1A1A1A;
    }
    </style>
""", unsafe_allow_html=True)

# Wrap app content in a clean container that offsets nicely against the grid-green background
st.markdown("<div class='main-panel'>", unsafe_allow_html=True)

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
    """Generates specific tags matching your exact parameters (Weather, Season, Occasion)."""
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
    st.markdown("## 👤 Account Setup")
    
    # Active Profile Selection using your updated user names
    current_user = st.radio("Who is using the closet right now?", ["Sarah's Closet", "Mark's Closet"])
    other_user = "Mark's Closet" if current_user == "Sarah's Closet" else "Sarah's Closet"
    
    # Profile Body Avatar Upload
    avatar_file = st.file_uploader(f"Upload standing full-body photo:", type=["png", "jpg", "jpeg"])
    if avatar_file:
        st.session_state.profiles[current_user]["avatar"] = Image.open(avatar_file)
        st.success("Avatar saved successfully!")

    st.write("---")
    st.markdown("## ➕ Add New Clothes")
    
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
st.markdown(f"<h1>🪞 {current_user} Dressing Room</h1>", unsafe_allow_html=True)

# Access Toggles (Borrowing Clothes Feature)
borrow_clothes = st.checkbox(f"🔄 Cross-reference and borrow clothing layers from {other_user}", value=False)
source_profile = st.session_state.profiles[current_user]

# --- GLOBAL FILTERS ---
st.markdown("<h3>🔍 Filter Options</h3>", unsafe_allow_html=True)
f_col1, f_col2, f_col3 = st.columns(3)

with f_col1:
    weather_filter = st.selectbox("Current Weather", ["All Weather", "Hot", "Cold", "Mild", "Rainy"])
with f_col2:
    season_filter = st.selectbox("Current Season", ["All Seasons", "Summer", "Winter", "Spring", "Fall"])
with f_col3:
    occasion_filter = st.selectbox("Target Occasion (Work, BBQ, Wedding, Mall...)", ["All Occasions", "Work", "Mall", "Wedding", "BBQ", "Date Night", "Casual"])

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
    st.markdown("<h3>👤 Silhouette Alignment</h3>", unsafe_allow_html=True)
    if source_profile["avatar"]:
        st.image(source_profile["avatar"], caption="Your Standing Fitting Silhouette", use_container_width=True)
    else:
        st.info("Upload your standing full-body photo in the sidebar to sync your virtual silhouette layout here.")

with view_col2:
    st.markdown("<h3>🔄 Mix & Match Carousel</h3>", unsafe_allow_html=True)
    
    if len(tops_pool) > 0 and len(bottoms_pool) > 0:
        top_sel = st.select_slider("Cycle Tops", options=range(len(tops_pool)), format_func=lambda x: f"Top {x+1} ({tops_pool[x]['source']})")
        bottom_sel = st.select_slider("Cycle Bottoms", options=range(len(bottoms_pool)), format_func=lambda x: f"Bottom {x+1} ({bottoms_pool[x]['source']})")
        
        active_top = tops_pool[top_sel]["item"]
        active_bottom = bottoms_pool[bottom_sel]["item"]
        
        outfit_display = st.columns(2)
        with outfit_display[0]:
            st.image(active_top["image"], caption="Selected Top", use_container_width=True)
            tag_html = "".join([f"<span class='tag-badge'>{tag}</span>" for tag in active_top["tags"]])
            st.markdown(tag_html, unsafe_allow_html=True)
            
        with outfit_display[1]:
            st.image(active_bottom["image"], caption="Selected Bottom", use_container_width=True)
            tag_html = "".join([f"<span class='tag-badge'>{tag}</span>" for tag in active_bottom["tags"]])
            st.markdown(tag_html, unsafe_allow_html=True)
            
        if acc_pool:
            acc_sel = st.selectbox("Mix Accessory overlay:", options=range(len(acc_pool)), format_func=lambda x: f"Accessory {x+1}")
            st.image(acc_pool[acc_sel]["item"]["image"], width=120)
            
        st.write("---")
        fb_cols = st.columns(2)
        current_combo_signature = f"{tops_pool[top_sel]['source']}_{tops_pool[top_sel]['index']}-{bottoms_pool[bottom_sel]['source']}_{bottoms_pool[bottom_sel]['index']}"
        
        if fb_cols[0].button("❤️ Save Combo"):
            st.session_state.history["liked_combos"].append(current_combo_signature)
            st.toast("Saved to your personal style catalog!")
        if fb_cols[1].button("❌ Dislike Combo"):
            st.session_state.history["disliked_combos"].append(current_combo_signature)
            st.toast("Muted combo from AI Stylist suggestions.")
            
    else:
        st.warning("No items match your active filters. Try toggling your weather/season dropdown configurations or adding more clothing uploads!")

st.markdown("</div>", unsafe_allow_html=True)