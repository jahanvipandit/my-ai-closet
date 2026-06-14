import streamlit as st
from PIL import Image
from rembg import remove
import io
import json
from google import genai

# Initialize Gemini Client
try:
    client = genai.Client()
except Exception:
    client = None

# --- BASIC APP CONFIG ---
st.set_page_config(page_title="Shared Virtual Closet", layout="wide")
st.title("🪞 Shared Virtual Dressing Room")

# --- SESSION STATE INITIALIZATION ---
if "profiles" not in st.session_state:
    st.session_state.profiles = {
        "Sarah's Closet": {"avatar": None, "closet": {"Tops": [], "Bottoms": [], "Accessories": []}},
        "Mark's Closet": {"avatar": None, "closet": {"Tops": [], "Bottoms": [], "Accessories": []}}
    }
if "history" not in st.session_state:
    st.session_state.history = {"liked_combos": [], "disliked_combos": []}

# Simple index tracking for cycling options safely
if "top_index" not in st.session_state:
    st.session_state.top_index = 0
if "bottom_index" not in st.session_state:
    st.session_state.bottom_index = 0

# --- IMAGES & TAGS BACKGROUND PIPELINES ---
def process_clothing_image(uploaded_file):
    input_bytes = uploaded_file.read()
    output_bytes = remove(input_bytes)
    return Image.open(io.BytesIO(output_bytes))

def ai_generate_clothing_tags(image, category):
    if not client:
        return ["Casual", "Spring", "Mall"]
    prompt = f"Analyze this {category} item. Return strictly a JSON list of 3 strings for its weather, season, and occasion tags. Example: ['Warm', 'Summer', 'Casual']"
    try:
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()
        response = client.models.generate_content(model='gemini-2.5-flash', contents=[prompt, img_bytes])
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_text)
    except Exception:
        return ["Casual", "Summer", "BBQ"]

# --- SIDEBAR OUTLET ---
with st.sidebar:
    st.header("👤 Account Setup")
    current_user = st.radio("Who is active?", ["Sarah's Closet", "Mark's Closet"])
    other_user = "Mark's Closet" if current_user == "Sarah's Closet" else "Sarah's Closet"
    
    avatar_file = st.file_uploader("Upload avatar photo:", type=["png", "jpg", "jpeg"])
    if avatar_file:
        st.session_state.profiles[current_user]["avatar"] = Image.open(avatar_file)
        st.success("Avatar uploaded!")

    st.write("---")
    st.header("➕ Add Clothes")
    upload_target = st.selectbox("Whose closet?", [current_user, other_user])
    cat = st.selectbox("Category", ["Tops", "Bottoms", "Accessories"])
    item_file = st.file_uploader("Item photo:", type=["png", "jpg", "jpeg"])
    
    if st.button("✨ Save Item") and item_file:
        with st.spinner("Processing..."):
            img = process_clothing_image(item_file)
            tags = ai_generate_clothing_tags(img, cat)
        st.session_state.profiles[upload_target]["closet"][cat].append({"image": img, "tags": tags})
        st.success("Item added successfully!")

# --- MAIN SCREEN INTERFACE ---
st.subheader(f"Dressing Room: {current_user}")
borrow_clothes = st.checkbox(f"🔄 Borrow clothing options from {other_user}", value=False)

# Build filtering loops
weather_filter = st.selectbox("Filter by Weather", ["All Weather", "Hot", "Cold", "Mild", "Rainy"])
season_filter = st.selectbox("Filter by Season", ["All Seasons", "Summer", "Winter", "Spring", "Fall"])
occasion_filter = st.selectbox("Filter by Occasion", ["All Occasions", "Work", "Mall", "Wedding", "BBQ", "Date Night", "Casual"])

def get_filtered_items(category):
    pool = []
    for item in st.session_state.profiles[current_user]["closet"][category]:
        pool.append(item)
    if borrow_clothes:
        for item in st.session_state.profiles[other_user]["closet"][category]:
            pool.append(item)
            
    filtered = []
    for item in pool:
        tags_lower = [t.lower() for t in item["tags"]]
        if weather_filter != "All Weather" and weather_filter.lower() not in tags_lower:
            continue
        if season_filter != "All Seasons" and season_filter.lower() not in tags_lower:
            continue
        if occasion_filter != "All Occasions" and occasion_filter.lower() not in tags_lower:
            continue
        filtered.append(item)
    return filtered

tops = get_filtered_items("Tops")
bottoms = get_filtered_items("Bottoms")

col1, col2 = st.columns([5, 5])

with col1:
    st.write("### 👤 Your Photo")
    if st.session_state.profiles[current_user]["avatar"]:
        st.image(st.session_state.profiles[current_user]["avatar"], use_container_width=True)
    else:
        st.info("Upload your full-body picture in the sidebar to see it here.")

with col2:
    st.write("### 🔄 Mix & Match Closet")
    
    if len(tops) > 0 and len(bottoms) > 0:
        # Prevent layout index boundary crashes
        if st.session_state.top_index >= len(tops):
            st.session_state.top_index = 0
        if st.session_state.bottom_index >= len(bottoms):
            st.session_state.bottom_index = 0
            
        # Cycle Action Buttons
        btn_c1, btn_c2 = st.columns(2)
        if btn_c1.button("👚 Next Top"):
            st.session_state.top_index = (st.session_state.top_index + 1) % len(tops)
        if btn_c2.button("👖 Next Bottom"):
            st.session_state.bottom_index = (st.session_state.bottom_index + 1) % len(bottoms)
            
        current_top = tops[st.session_state.top_index]
        current_bottom = bottoms[st.session_state.bottom_index]
        
        # Display chosen items
        st.image(current_top["image"], caption="Active Top Selection", width=250)
        st.write("Top Tags: " + ", ".join(current_top["tags"]))
        
        st.image(current_bottom["image"], caption="Active Bottom Selection", width=250)
        st.write("Bottom Tags: " + ", ".join(current_bottom["tags"]))
        
        st.write("---")
        if st.button("❤️ Save Outfit Combination"):
            st.toast("Saved to your preferences!")
    else:
        st.warning("No items match your active filters. Upload a Top and a Bottom in the sidebar to start styling!")
