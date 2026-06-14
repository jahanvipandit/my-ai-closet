import streamlit as st
from PIL import Image
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

# --- APP CONFIG ---
st.set_page_config(page_title="Our Virtual Closet 👗", layout="wide", page_icon="🪞")

st.markdown("""
<style>
    /* ── Background & base text ── */
    .stApp, .main, [data-testid="stAppViewContainer"] {
        background-color: #1a472a !important;
    }
    section[data-testid="stSidebar"] {
        background-color: #145a32 !important;
    }
    section[data-testid="stSidebar"] * {
        color: #ffb6c1 !important;
    }

    /* ── All general text → pink ── */
    html, body, [class*="css"], p, span, label, div {
        color: #ffb6c1 !important;
    }

    /* ── Headings ── */
    h1, h2, h3, h4, h5, h6,
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #ff69b4 !important;
        font-family: 'Georgia', serif;
    }

    /* ── Buttons ── */
    .stButton > button {
        background-color: #ff69b4 !important;
        color: #1a472a !important;
        border: none !important;
        border-radius: 24px !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
        padding: 0.45rem 1.1rem !important;
        transition: background-color 0.2s;
    }
    .stButton > button:hover {
        background-color: #ff1493 !important;
        color: white !important;
    }

    /* ── Radio / checkbox labels ── */
    .stRadio label, .stCheckbox label {
        color: #ffb6c1 !important;
        font-weight: 600;
    }

    /* ── Selectbox & file uploader text ── */
    .stSelectbox label, .stFileUploader label {
        color: #ffb6c1 !important;
    }
    .stSelectbox > div > div {
        background-color: #145a32 !important;
        color: #ffb6c1 !important;
        border: 1px solid #ff69b4 !important;
        border-radius: 10px !important;
    }

    /* ── Info / warning / success boxes ── */
    .stAlert {
        border-radius: 12px !important;
    }

    /* ── Divider ── */
    hr { border-color: #ff69b4 !important; opacity: 0.4; }

    /* ── Caption text ── */
    .stCaption, small { color: #f9a8d4 !important; }

    /* ── Expander header ── */
    details summary {
        color: #ff69b4 !important;
        font-weight: 600;
    }

    /* ── Image captions ── */
    figcaption { color: #f9a8d4 !important; }
</style>
""", unsafe_allow_html=True)

st.title("🪞 Our Shared Virtual Closet")

# --- GEMINI CLIENT ---
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
if "profiles" not in st.session_state:
    st.session_state.profiles = {
        "My Closet": {
            "avatar": None,
            "name": "Me",
            "closet": {"Tops": [], "Bottoms": [], "Shoes": [], "Accessories": []}
        },
        "Partner's Closet": {
            "avatar": None,
            "name": "Partner",
            "closet": {"Tops": [], "Bottoms": [], "Shoes": [], "Accessories": []}
        }
    }

for key in ["top_index", "bottom_index", "shoe_index"]:
    if key not in st.session_state:
        st.session_state[key] = 0

if "ai_suggestion" not in st.session_state:
    st.session_state.ai_suggestion = ""
if "saved_outfits" not in st.session_state:
    st.session_state.saved_outfits = []

# --- IMAGE HELPERS ---
def remove_background_simple(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    data = image.getdata()
    new_data = []
    for r, g, b, a in data:
        if r > 200 and g > 200 and b > 200:
            new_data.append((r, g, b, 0))
        else:
            new_data.append((r, g, b, a))
    image.putdata(new_data)
    return image

def process_clothing_image(uploaded_file) -> Image.Image:
    img = Image.open(uploaded_file).convert("RGBA")
    return remove_background_simple(img)

def image_to_base64(image: Image.Image) -> str:
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
    if not client:
        defaults = {
            "Tops":        ["Mild", "Spring", "Casual"],
            "Bottoms":     ["Warm", "Summer", "Casual"],
            "Shoes":       ["All Weather", "All Season", "Casual"],
            "Accessories": ["All Weather", "All Season", "Casual"]
        }
        return defaults.get(category, ["Casual", "All Season", "Everyday"])

    prompt = (
        f"You are a fashion stylist analyzing a clothing item photo.\n"
        f"Category: {category}\n"
        f"Return ONLY a valid JSON list of exactly 3 strings: [weather_tag, season_tag, occasion_tag].\n"
        f"Weather options: Hot, Warm, Mild, Cold, Rainy, All Weather\n"
        f"Season options: Spring, Summer, Fall, Winter, All Season\n"
        f"Occasion options: Casual, Work, Date Night, Wedding, BBQ, Gym, Mall, Going Out\n"
        f'Example: ["Warm", "Summer", "Casual"]\n'
        f"Return nothing else."
    )
    try:
        img_bytes = image_to_bytes(image)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[types.Part.from_bytes(data=img_bytes, mime_type="image/png"), prompt]
        )
        cleaned = response.text.strip().replace("```json", "").replace("```", "").strip()
        tags = json.loads(cleaned)
        if isinstance(tags, list) and len(tags) == 3:
            return tags
    except Exception:
        pass
    return ["Casual", "All Season", "Everyday"]


def ai_suggest_outfit(top, bottom, shoes=None, occasion="Casual") -> str:
    if not client:
        return (
            f"This combo looks great for a {occasion} outing! "
            "The pieces work well together. Consider adding a simple accessory to finish the look."
        )
    top_tags    = ", ".join(top["tags"])   if top    else "none"
    bottom_tags = ", ".join(bottom["tags"]) if bottom else "none"
    shoe_tags   = ", ".join(shoes["tags"]) if shoes  else "not selected"
    prompt = (
        f"You are a friendly personal stylist giving a brief outfit review.\n"
        f"Top tags: {top_tags}\nBottom tags: {bottom_tags}\nShoes tags: {shoe_tags}\nOccasion: {occasion}\n"
        f"Give 2-3 warm, encouraging sentences: does it work? what to add or change?"
    )
    try:
        response = client.models.generate_content(model="gemini-2.0-flash", contents=[prompt])
        return response.text.strip()
    except Exception:
        return "This outfit looks great! You're all set. 💕"


def ai_best_outfit(tops, bottoms, shoes_list, occasion) -> dict | None:
    if not tops or not bottoms:
        return None
    if not client:
        return {
            "top":    random.choice(tops),
            "bottom": random.choice(bottoms),
            "shoes":  random.choice(shoes_list) if shoes_list else None
        }
    tops_desc    = "\n".join([f"Top {i}: {', '.join(t['tags'])}"    for i, t in enumerate(tops)])
    bottoms_desc = "\n".join([f"Bottom {i}: {', '.join(b['tags'])}" for i, b in enumerate(bottoms)])
    shoes_desc   = "\n".join([f"Shoes {i}: {', '.join(s['tags'])}"  for i, s in enumerate(shoes_list)]) if shoes_list else "None"
    prompt = (
        f"Pick the best outfit for: {occasion}\n\n"
        f"Tops:\n{tops_desc}\n\nBottoms:\n{bottoms_desc}\n\nShoes:\n{shoes_desc}\n\n"
        f'Return ONLY JSON like: {{"top": 0, "bottom": 1, "shoes": 0}} — use null if no shoes. No extra text.'
    )
    try:
        response = client.models.generate_content(model="gemini-2.0-flash", contents=[prompt])
        cleaned = response.text.strip().replace("```json", "").replace("```", "").strip()
        idx = json.loads(cleaned)
        return {
            "top":    tops[idx.get("top", 0)],
            "bottom": bottoms[idx.get("bottom", 0)],
            "shoes":  shoes_list[idx["shoes"]] if shoes_list and idx.get("shoes") is not None else None
        }
    except Exception:
        return {
            "top":    random.choice(tops),
            "bottom": random.choice(bottoms),
            "shoes":  random.choice(shoes_list) if shoes_list else None
        }


# ══════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════
with st.sidebar:
    st.header("👤 Active Profile")
    current_user = st.radio("Who's styling?", ["My Closet", "Partner's Closet"])
    other_user   = "Partner's Closet" if current_user == "My Closet" else "My Closet"

    # ── Profile name editing ──
    st.divider()
    st.subheader("✏️ Profile Names")
    col_n1, col_n2 = st.columns(2)
    with col_n1:
        new_name_me = st.text_input("Your name", value=st.session_state.profiles["My Closet"]["name"], key="name_me")
        st.session_state.profiles["My Closet"]["name"] = new_name_me
    with col_n2:
        new_name_partner = st.text_input("Partner's name", value=st.session_state.profiles["Partner's Closet"]["name"], key="name_partner")
        st.session_state.profiles["Partner's Closet"]["name"] = new_name_partner

    # ── Avatar upload for BOTH profiles ──
    st.divider()
    st.subheader("📸 Profile Photos")

    av_col1, av_col2 = st.columns(2)

    with av_col1:
        me_name = st.session_state.profiles["My Closet"]["name"]
        st.caption(f"**{me_name}**")
        av_me = st.file_uploader(f"Upload {me_name}'s photo", type=["png","jpg","jpeg"], key="av_me")
        if av_me:
            st.session_state.profiles["My Closet"]["avatar"] = image_to_base64(Image.open(av_me))
            st.success("Saved!")
        if st.session_state.profiles["My Closet"]["avatar"]:
            st.image(base64_to_image(st.session_state.profiles["My Closet"]["avatar"]), use_container_width=True)

    with av_col2:
        partner_name = st.session_state.profiles["Partner's Closet"]["name"]
        st.caption(f"**{partner_name}**")
        av_partner = st.file_uploader(f"Upload {partner_name}'s photo", type=["png","jpg","jpeg"], key="av_partner")
        if av_partner:
            st.session_state.profiles["Partner's Closet"]["avatar"] = image_to_base64(Image.open(av_partner))
            st.success("Saved!")
        if st.session_state.profiles["Partner's Closet"]["avatar"]:
            st.image(base64_to_image(st.session_state.profiles["Partner's Closet"]["avatar"]), use_container_width=True)

    # ── Add clothes ──
    st.divider()
    st.subheader("➕ Add Clothes")

    upload_target = st.selectbox("Add to whose closet?", [current_user, other_user])
    cat           = st.selectbox("Category", ["Tops", "Bottoms", "Shoes", "Accessories"])
    item_file     = st.file_uploader("Photo of item", type=["png","jpg","jpeg"], key="item_upload")

    if not client:
        st.caption("💡 Add GOOGLE_API_KEY to Streamlit secrets for AI features.")

    if st.button("✨ Save Item") and item_file:
        with st.spinner("Processing & tagging..."):
            img  = process_clothing_image(item_file)
            tags = ai_generate_tags(img, cat)
            b64  = image_to_base64(img)
        st.session_state.profiles[upload_target]["closet"][cat].append({"image_b64": b64, "tags": tags})
        st.success(f"Added! Tags: {', '.join(tags)}")
        st.rerun()

    # ── Closet counts ──
    st.divider()
    st.caption(f"**{st.session_state.profiles[current_user]['name']}'s closet:**")
    for cat_name, items in st.session_state.profiles[current_user]["closet"].items():
        st.caption(f"  {cat_name}: {len(items)}")


# ══════════════════════════════════════════════
# MAIN AREA
# ══════════════════════════════════════════════
me_name      = st.session_state.profiles["My Closet"]["name"]
partner_name = st.session_state.profiles["Partner's Closet"]["name"]
cur_name     = st.session_state.profiles[current_user]["name"]

st.subheader(f"👗 {cur_name}'s Dressing Room")

borrow = st.checkbox(f"🔄 Also include {st.session_state.profiles[other_user]['name']}'s clothes", value=False)

fc1, fc2, fc3 = st.columns(3)
with fc1: weather_filter  = st.selectbox("Weather",  ["All Weather","Hot","Warm","Mild","Cold","Rainy"])
with fc2: season_filter   = st.selectbox("Season",   ["All Season","Spring","Summer","Fall","Winter"])
with fc3: occasion_filter = st.selectbox("Occasion", ["Casual","Work","Date Night","Wedding","BBQ","Gym","Mall","Going Out"])

def get_items(category):
    pool = list(st.session_state.profiles[current_user]["closet"][category])
    if borrow:
        pool += list(st.session_state.profiles[other_user]["closet"][category])
    filtered = []
    for item in pool:
        tl = [t.lower() for t in item["tags"]]
        if weather_filter  != "All Weather" and weather_filter.lower()  not in tl: continue
        if season_filter   != "All Season"  and season_filter.lower()   not in tl: continue
        filtered.append(item)
    return filtered

tops       = get_items("Tops")
bottoms    = get_items("Bottoms")
shoes_list = get_items("Shoes")

# Clamp indices
if tops       and st.session_state.top_index    >= len(tops):       st.session_state.top_index    = 0
if bottoms    and st.session_state.bottom_index >= len(bottoms):    st.session_state.bottom_index = 0
if shoes_list and st.session_state.shoe_index   >= len(shoes_list): st.session_state.shoe_index   = 0

st.divider()

# ── Two-column layout: avatar | outfit ──
avatar_col, outfit_col = st.columns([4, 6])

with avatar_col:
    st.subheader(f"📸 {cur_name}'s Photo")
    if st.session_state.profiles[current_user]["avatar"]:
        st.image(base64_to_image(st.session_state.profiles[current_user]["avatar"]), use_container_width=True)
    else:
        st.info(f"Upload {cur_name}'s photo in the sidebar to see it here.")

with outfit_col:
    st.subheader("✨ Mix & Match")

    if not tops and not bottoms:
        st.warning("No items match your filters. Add a Top and Bottom in the sidebar to get started!")
    else:
        # Navigation row
        b1, b2, b3, b4 = st.columns(4)
        if tops       and b1.button("👚 Next Top"):    st.session_state.top_index    = (st.session_state.top_index    + 1) % len(tops)
        if bottoms    and b2.button("👖 Next Bottom"): st.session_state.bottom_index = (st.session_state.bottom_index + 1) % len(bottoms)
        if shoes_list and b3.button("👟 Next Shoes"):  st.session_state.shoe_index   = (st.session_state.shoe_index   + 1) % len(shoes_list)
        if b4.button("🎲 Shuffle"):
            if tops:       st.session_state.top_index    = random.randint(0, len(tops)-1)
            if bottoms:    st.session_state.bottom_index = random.randint(0, len(bottoms)-1)
            if shoes_list: st.session_state.shoe_index   = random.randint(0, len(shoes_list)-1)

        current_top    = tops[st.session_state.top_index]       if tops       else None
        current_bottom = bottoms[st.session_state.bottom_index] if bottoms    else None
        current_shoes  = shoes_list[st.session_state.shoe_index] if shoes_list else None

        ic1, ic2, ic3 = st.columns(3)
        if current_top:
            with ic1:
                st.image(base64_to_image(current_top["image_b64"]), caption="Top", use_container_width=True)
                st.caption(" · ".join(current_top["tags"]))
        if current_bottom:
            with ic2:
                st.image(base64_to_image(current_bottom["image_b64"]), caption="Bottom", use_container_width=True)
                st.caption(" · ".join(current_bottom["tags"]))
        if current_shoes:
            with ic3:
                st.image(base64_to_image(current_shoes["image_b64"]), caption="Shoes", use_container_width=True)
                st.caption(" · ".join(current_shoes["tags"]))

        st.divider()

        # Action buttons
        ac1, ac2, ac3 = st.columns(3)

        if ac1.button("💬 AI Outfit Tip"):
            with st.spinner("Asking your stylist..."):
                st.session_state.ai_suggestion = ai_suggest_outfit(current_top, current_bottom, current_shoes, occasion_filter)

        if ac2.button("🎯 AI Best Pick"):
            with st.spinner("Finding the best combo..."):
                result = ai_best_outfit(tops, bottoms, shoes_list, occasion_filter)
                if result:
                    if result["top"]    and result["top"]    in tops:       st.session_state.top_index    = tops.index(result["top"])
                    if result["bottom"] and result["bottom"] in bottoms:    st.session_state.bottom_index = bottoms.index(result["bottom"])
                    if result["shoes"]  and result["shoes"]  in shoes_list: st.session_state.shoe_index   = shoes_list.index(result["shoes"])
                    st.session_state.ai_suggestion = "🎯 AI picked this outfit for you!"
            st.rerun()

        if ac3.button("❤️ Save Outfit"):
            st.session_state.saved_outfits.append({
                "user":        cur_name,
                "occasion":    occasion_filter,
                "top_tags":    current_top["tags"]    if current_top    else [],
                "bottom_tags": current_bottom["tags"] if current_bottom else [],
                "shoe_tags":   current_shoes["tags"]  if current_shoes  else []
            })
            st.toast("Outfit saved! ❤️")

        if st.session_state.ai_suggestion:
            st.info(f"💬 {st.session_state.ai_suggestion}")

# ── Saved outfits log ──
if st.session_state.saved_outfits:
    st.divider()
    st.subheader("❤️ Saved Outfits")
    for i, outfit in enumerate(reversed(st.session_state.saved_outfits)):
        n = len(st.session_state.saved_outfits) - i
        with st.expander(f"Outfit {n} — {outfit['occasion']} ({outfit['user']})"):
            st.write(f"**Top:** {', '.join(outfit['top_tags']) or 'N/A'}")
            st.write(f"**Bottom:** {', '.join(outfit['bottom_tags']) or 'N/A'}")
            st.write(f"**Shoes:** {', '.join(outfit['shoe_tags']) or 'N/A'}")
