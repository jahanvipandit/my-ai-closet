import streamlit as st
from PIL import Image, ImageEnhance
import io
import json
import random
import base64

# Try to import google genai - gracefully degrade if missing
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# --- BASIC APP CONFIG ---
st.set_page_config(page_title="Our Virtual Closet", layout="wide", page_icon="🪞")

st.markdown("""
<style>
    .main { background-color: #fdf8f5; }
    .stButton>button {
        border-radius: 20px;
        border: 1.5px solid #d4a5a5;
        background-color: #fff0f0;
        color: #5a3a3a;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #f7c5c5;
        border-color: #b07070;
    }
    h1, h2, h3 { color: #4a2c2c; }
    .outfit-box {
        background: white;
        border-radius: 16px;
        padding: 1.2rem;
        border: 1px solid #f0d8d8;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("🪞 Our Shared Virtual Closet")

# --- GEMINI CLIENT SETUP ---
def get_gemini_client():
    if not GENAI_AVAILABLE:
        return None
    try:
        api_key = st.secrets.get("GOOGLE_API_KEY", None)
        if not api_key:
            return None
        return genai.Client(api_key=api_key)
    except Exception:
        return None

client = get_gemini_client()

# --- SESSION STATE ---
DEFAULT_PROFILES = {
    "My Closet": {"avatar": None, "closet": {"Tops": [], "Bottoms": [], "Shoes": [], "Accessories": []}},
    "Partner's Closet": {"avatar": None, "closet": {"Tops": [], "Bottoms": [], "Shoes": [], "Accessories": []}}
}

if "profiles" not in st.session_state:
    st.session_state.profiles = DEFAULT_PROFILES

if "top_index" not in st.session_state:
    st.session_state.top_index = 0
if "bottom_index" not in st.session_state:
    st.session_state.bottom_index = 0
if "shoe_index" not in st.session_state:
    st.session_state.shoe_index = 0
if "ai_suggestion" not in st.session_state:
    st.session_state.ai_suggestion = ""
if "saved_outfits" not in st.session_state:
    st.session_state.saved_outfits = []

# --- IMAGE HELPERS ---
def remove_background_simple(image: Image.Image) -> Image.Image:
    """
    Lightweight background removal using PIL only — no heavy ML models.
    Converts to RGBA and makes near-white pixels transparent.
    Works well for clothes photos taken on a white/light background.
    """
    image = image.convert("RGBA")
    data = image.getdata()
    new_data = []
    for r, g, b, a in data:
        # Make pixels that are close to white transparent
        if r > 200 and g > 200 and b > 200:
            new_data.append((r, g, b, 0))
        else:
            new_data.append((r, g, b, a))
    image.putdata(new_data)
    return image

def process_clothing_image(uploaded_file) -> Image.Image:
    img = Image.open(uploaded_file)
    img = img.convert("RGBA")
    img = remove_background_simple(img)
    return img

def image_to_base64(image: Image.Image) -> str:
    """Convert PIL image to base64 string for storage."""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def base64_to_image(b64_str: str) -> Image.Image:
    buf = io.BytesIO(base64.b64decode(b64_str))
    return Image.open(buf)

def image_to_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()

# --- AI FUNCTIONS ---
def ai_generate_tags(image: Image.Image, category: str) -> list:
    """Generate weather/season/occasion tags using Gemini."""
    if not client:
        defaults = {
            "Tops": ["Mild", "Spring", "Casual"],
            "Bottoms": ["Warm", "Summer", "Casual"],
            "Shoes": ["All Weather", "All Season", "Casual"],
            "Accessories": ["All Weather", "All Season", "Casual"]
        }
        return defaults.get(category, ["Casual", "Spring", "Everyday"])

    prompt = (
        f"You are a fashion stylist analyzing a clothing item photo.\n"
        f"Category: {category}\n"
        f"Return ONLY a valid JSON list of exactly 3 strings: [weather_tag, season_tag, occasion_tag].\n"
        f"Weather options: Hot, Warm, Mild, Cold, Rainy, All Weather\n"
        f"Season options: Spring, Summer, Fall, Winter, All Season\n"
        f"Occasion options: Casual, Work, Date Night, Wedding, BBQ, Gym, Mall, Going Out\n"
        f"Example output: [\"Warm\", \"Summer\", \"Casual\"]\n"
        f"Return nothing else — no explanation, no markdown."
    )
    try:
        img_bytes = image_to_bytes(image)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                prompt
            ]
        )
        cleaned = response.text.strip().replace("```json", "").replace("```", "").strip()
        tags = json.loads(cleaned)
        if isinstance(tags, list) and len(tags) == 3:
            return tags
        return ["Casual", "All Season", "Everyday"]
    except Exception:
        return ["Casual", "All Season", "Everyday"]


def ai_suggest_outfit(top, bottom, shoes=None, occasion="Casual") -> str:
    """Get AI styling advice for a current outfit combo."""
    if not client:
        return (
            f"This combo looks great for a {occasion} outing! "
            "The top and bottom complement each other well. "
            "Consider adding a belt or simple jewelry to elevate the look."
        )

    top_tags = ", ".join(top["tags"]) if top else "none"
    bottom_tags = ", ".join(bottom["tags"]) if bottom else "none"
    shoe_tags = ", ".join(shoes["tags"]) if shoes else "not selected"

    prompt = (
        f"You are a friendly personal stylist giving a brief outfit review.\n"
        f"Outfit details:\n"
        f"- Top tags: {top_tags}\n"
        f"- Bottom tags: {bottom_tags}\n"
        f"- Shoes tags: {shoe_tags}\n"
        f"- Occasion: {occasion}\n"
        f"Give 2-3 sentences of styling advice: does it work? what to add or change? Keep it warm and encouraging."
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt]
        )
        return response.text.strip()
    except Exception:
        return "This outfit looks great! You're all set."


def ai_random_outfit_suggestion(tops, bottoms, shoes_list, occasion) -> dict | None:
    """Pick the best outfit combo for a given occasion using AI reasoning."""
    if not tops or not bottoms:
        return None

    if not client:
        # Random fallback
        return {
            "top": random.choice(tops),
            "bottom": random.choice(bottoms),
            "shoes": random.choice(shoes_list) if shoes_list else None
        }

    # Build a description of available items
    tops_desc = "\n".join([f"Top {i}: {', '.join(t['tags'])}" for i, t in enumerate(tops)])
    bottoms_desc = "\n".join([f"Bottom {i}: {', '.join(b['tags'])}" for i, b in enumerate(bottoms)])
    shoes_desc = "\n".join([f"Shoes {i}: {', '.join(s['tags'])}" for i, s in enumerate(shoes_list)]) if shoes_list else "None available"

    prompt = (
        f"You are a stylist. Pick the best outfit combo for occasion: {occasion}\n\n"
        f"Available Tops:\n{tops_desc}\n\n"
        f"Available Bottoms:\n{bottoms_desc}\n\n"
        f"Available Shoes:\n{shoes_desc}\n\n"
        f"Return ONLY a JSON object like: {{\"top\": 0, \"bottom\": 1, \"shoes\": 0}}\n"
        f"Use index numbers. If no shoes available, set shoes to null. No extra text."
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt]
        )
        cleaned = response.text.strip().replace("```json", "").replace("```", "").strip()
        indices = json.loads(cleaned)
        return {
            "top": tops[indices.get("top", 0)] if tops else None,
            "bottom": bottoms[indices.get("bottom", 0)] if bottoms else None,
            "shoes": shoes_list[indices["shoes"]] if shoes_list and indices.get("shoes") is not None else None
        }
    except Exception:
        return {
            "top": random.choice(tops),
            "bottom": random.choice(bottoms),
            "shoes": random.choice(shoes_list) if shoes_list else None
        }

# --- SIDEBAR ---
with st.sidebar:
    st.header("👤 Who's Styling?")
    current_user = st.radio("Active profile:", ["My Closet", "Partner's Closet"])
    other_user = "Partner's Closet" if current_user == "My Closet" else "My Closet"

    st.write("**Upload your photo:**")
    avatar_file = st.file_uploader("Full-body photo", type=["png", "jpg", "jpeg"], key="avatar_upload")
    if avatar_file:
        st.session_state.profiles[current_user]["avatar"] = image_to_base64(Image.open(avatar_file))
        st.success("Photo saved!")

    if st.session_state.profiles[current_user]["avatar"]:
        st.image(base64_to_image(st.session_state.profiles[current_user]["avatar"]), use_container_width=True)

    st.divider()
    st.header("➕ Add Clothes")

    upload_target = st.selectbox("Add to:", [current_user, other_user])
    cat = st.selectbox("Category", ["Tops", "Bottoms", "Shoes", "Accessories"])
    item_file = st.file_uploader("Photo of item", type=["png", "jpg", "jpeg"], key="item_upload")

    if not client:
        st.caption("💡 Add `GOOGLE_API_KEY` to Streamlit secrets for AI tagging & suggestions.")

    if st.button("✨ Save Item") and item_file:
        with st.spinner("Processing image & generating tags..."):
            img = process_clothing_image(item_file)
            tags = ai_generate_tags(img, cat)
            img_b64 = image_to_base64(img)
        st.session_state.profiles[upload_target]["closet"][cat].append({
            "image_b64": img_b64,
            "tags": tags
        })
        st.success(f"Added to {upload_target}! Tags: {', '.join(tags)}")
        st.rerun()

    st.divider()
    # Show closet counts
    st.caption(f"**{current_user}:**")
    for cat_name, items in st.session_state.profiles[current_user]["closet"].items():
        st.caption(f"  {cat_name}: {len(items)} item(s)")

# --- MAIN AREA ---
borrow = st.checkbox(f"🔄 Include {other_user}'s clothes in mix", value=False)

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    weather_filter = st.selectbox("Weather", ["All Weather", "Hot", "Warm", "Mild", "Cold", "Rainy"])
with col_f2:
    season_filter = st.selectbox("Season", ["All Season", "Spring", "Summer", "Fall", "Winter"])
with col_f3:
    occasion_filter = st.selectbox("Occasion", ["Casual", "Work", "Date Night", "Wedding", "BBQ", "Gym", "Mall", "Going Out"])

def get_items(category):
    pool = list(st.session_state.profiles[current_user]["closet"][category])
    if borrow:
        pool += list(st.session_state.profiles[other_user]["closet"][category])
    filtered = []
    for item in pool:
        tags_lower = [t.lower() for t in item["tags"]]
        if weather_filter != "All Weather" and weather_filter.lower() not in tags_lower:
            continue
        if season_filter != "All Season" and season_filter.lower() not in tags_lower:
            continue
        filtered.append(item)
    return filtered

tops = get_items("Tops")
bottoms = get_items("Bottoms")
shoes_list = get_items("Shoes")

# Clamp indices
if tops and st.session_state.top_index >= len(tops):
    st.session_state.top_index = 0
if bottoms and st.session_state.bottom_index >= len(bottoms):
    st.session_state.bottom_index = 0
if shoes_list and st.session_state.shoe_index >= len(shoes_list):
    st.session_state.shoe_index = 0

st.divider()

# --- DRESSING ROOM ---
main_col, outfit_col = st.columns([4, 6])

with main_col:
    st.subheader("📸 Your Photo")
    if st.session_state.profiles[current_user]["avatar"]:
        st.image(base64_to_image(st.session_state.profiles[current_user]["avatar"]), use_container_width=True)
    else:
        st.info("Upload your full-body photo in the sidebar.")

with outfit_col:
    st.subheader("👗 Mix & Match")

    if not tops and not bottoms:
        st.warning("No items yet! Add a Top and Bottom in the sidebar to start.")
    else:
        # Navigation buttons
        b1, b2, b3, b4 = st.columns(4)
        if tops:
            if b1.button("👚 Next Top"):
                st.session_state.top_index = (st.session_state.top_index + 1) % len(tops)
        if bottoms:
            if b2.button("👖 Next Bottom"):
                st.session_state.bottom_index = (st.session_state.bottom_index + 1) % len(bottoms)
        if shoes_list:
            if b3.button("👟 Next Shoes"):
                st.session_state.shoe_index = (st.session_state.shoe_index + 1) % len(shoes_list)
        if b4.button("🎲 Randomize"):
            if tops: st.session_state.top_index = random.randint(0, len(tops)-1)
            if bottoms: st.session_state.bottom_index = random.randint(0, len(bottoms)-1)
            if shoes_list: st.session_state.shoe_index = random.randint(0, len(shoes_list)-1)

        # Display current combo
        current_top = tops[st.session_state.top_index] if tops else None
        current_bottom = bottoms[st.session_state.bottom_index] if bottoms else None
        current_shoes = shoes_list[st.session_state.shoe_index] if shoes_list else None

        item_cols = st.columns(3)
        if current_top:
            with item_cols[0]:
                st.image(base64_to_image(current_top["image_b64"]), caption="Top", use_container_width=True)
                st.caption(" · ".join(current_top["tags"]))
        if current_bottom:
            with item_cols[1]:
                st.image(base64_to_image(current_bottom["image_b64"]), caption="Bottom", use_container_width=True)
                st.caption(" · ".join(current_bottom["tags"]))
        if current_shoes:
            with item_cols[2]:
                st.image(base64_to_image(current_shoes["image_b64"]), caption="Shoes", use_container_width=True)
                st.caption(" · ".join(current_shoes["tags"]))

        st.divider()

        # AI suggestion buttons
        ai_col1, ai_col2, save_col = st.columns(3)

        if ai_col1.button("✨ AI Outfit Tip"):
            with st.spinner("Getting styling advice..."):
                st.session_state.ai_suggestion = ai_suggest_outfit(
                    current_top, current_bottom, current_shoes, occasion_filter
                )

        if ai_col2.button("🎯 AI Pick Best Outfit"):
            with st.spinner("Finding your best combo..."):
                result = ai_random_outfit_suggestion(tops, bottoms, shoes_list, occasion_filter)
                if result:
                    if result["top"] and tops:
                        st.session_state.top_index = tops.index(result["top"]) if result["top"] in tops else 0
                    if result["bottom"] and bottoms:
                        st.session_state.bottom_index = bottoms.index(result["bottom"]) if result["bottom"] in bottoms else 0
                    if result["shoes"] and shoes_list:
                        st.session_state.shoe_index = shoes_list.index(result["shoes"]) if result["shoes"] in shoes_list else 0
                    st.session_state.ai_suggestion = "✨ AI picked this outfit for you based on your filters and occasion!"
                st.rerun()

        if save_col.button("❤️ Save Outfit"):
            outfit = {
                "user": current_user,
                "occasion": occasion_filter,
                "top_tags": current_top["tags"] if current_top else [],
                "bottom_tags": current_bottom["tags"] if current_bottom else [],
                "shoe_tags": current_shoes["tags"] if current_shoes else []
            }
            st.session_state.saved_outfits.append(outfit)
            st.toast("Outfit saved! ❤️")

        if st.session_state.ai_suggestion:
            st.info(f"💬 {st.session_state.ai_suggestion}")

# --- SAVED OUTFITS ---
if st.session_state.saved_outfits:
    st.divider()
    st.subheader("❤️ Saved Outfits")
    for i, outfit in enumerate(reversed(st.session_state.saved_outfits)):
        with st.expander(f"Outfit {len(st.session_state.saved_outfits) - i} — {outfit['occasion']} ({outfit['user']})"):
            st.write(f"**Top:** {', '.join(outfit['top_tags']) or 'N/A'}")
            st.write(f"**Bottom:** {', '.join(outfit['bottom_tags']) or 'N/A'}")
            st.write(f"**Shoes:** {', '.join(outfit['shoe_tags']) or 'N/A'}")
