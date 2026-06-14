import streamlit as st
from PIL import Image
import io
import json
import random
import base64
import requests

# ── Optional: Google Sheets ──
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

# ── Optional: Gemini ──
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# ══════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════
st.set_page_config(page_title="Our Virtual Closet 👗", layout="wide", page_icon="🪞")

st.markdown("""
<style>
    .stApp, .main, [data-testid="stAppViewContainer"] {
        background-color: #1a472a !important;
    }
    section[data-testid="stSidebar"] {
        background-color: #145a32 !important;
    }
    section[data-testid="stSidebar"] * { color: #ffb6c1 !important; }
    html, body, [class*="css"], p, span, label, div { color: #ffb6c1 !important; }
    h1, h2, h3, h4, h5, h6,
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #ff69b4 !important;
        font-family: 'Georgia', serif;
    }
    .stButton > button {
        background-color: #ff69b4 !important;
        color: #1a472a !important;
        border: none !important;
        border-radius: 24px !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
        padding: 0.45rem 1.1rem !important;
    }
    .stButton > button:hover { background-color: #ff1493 !important; color: white !important; }
    .stRadio label, .stCheckbox label { color: #ffb6c1 !important; font-weight: 600; }
    .stSelectbox label, .stFileUploader label { color: #ffb6c1 !important; }
    .stSelectbox > div > div {
        background-color: #145a32 !important;
        color: #ffb6c1 !important;
        border: 1px solid #ff69b4 !important;
        border-radius: 10px !important;
    }
    hr { border-color: #ff69b4 !important; opacity: 0.4; }
    .stCaption, small { color: #f9a8d4 !important; }
    details summary { color: #ff69b4 !important; font-weight: 600; }
    figcaption { color: #f9a8d4 !important; }
    .stTextInput > div > div > input {
        background-color: #145a32 !important;
        color: #ffb6c1 !important;
        border: 1px solid #ff69b4 !important;
        border-radius: 8px !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🪞 Our Shared Virtual Closet")

# ══════════════════════════════════════════════
# CLIENTS
# ══════════════════════════════════════════════
def get_gemini_client():
    if not GENAI_AVAILABLE:
        return None
    try:
        key = st.secrets.get("GOOGLE_API_KEY", None)
        return genai.Client(api_key=key) if key else None
    except Exception:
        return None

def get_removebg_key():
    try:
        return st.secrets.get("REMOVEBG_API_KEY", None)
    except Exception:
        return None

def get_gsheets_client():
    if not GSPREAD_AVAILABLE:
        return None
    try:
        creds_dict = st.secrets.get("GSHEETS_CREDENTIALS", None)
        if not creds_dict:
            return None
        scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(dict(creds_dict), scopes=scopes)
        return gspread.authorize(creds)
    except Exception:
        return None

gemini_client   = get_gemini_client()
removebg_key    = get_removebg_key()
gsheets_client  = get_gsheets_client()

# ══════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════
PROFILE_KEYS = ["My Closet", "Partner's Closet"]
CATEGORIES   = ["Tops", "Bottoms", "Shoes", "Accessories"]

def empty_profile(name):
    return {"avatar": None, "name": name, "closet": {c: [] for c in CATEGORIES}}

if "profiles" not in st.session_state:
    st.session_state.profiles = {
        "My Closet":        empty_profile("Me"),
        "Partner's Closet": empty_profile("Partner"),
    }
if "top_index"      not in st.session_state: st.session_state.top_index    = 0
if "bottom_index"   not in st.session_state: st.session_state.bottom_index = 0
if "shoe_index"     not in st.session_state: st.session_state.shoe_index   = 0
if "ai_suggestion"  not in st.session_state: st.session_state.ai_suggestion = ""
if "saved_outfits"  not in st.session_state: st.session_state.saved_outfits = []
if "gs_sheet_url"   not in st.session_state: st.session_state.gs_sheet_url  = ""

# ══════════════════════════════════════════════
# IMAGE HELPERS
# ══════════════════════════════════════════════
def image_to_base64(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def base64_to_image(b64: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(b64)))

def image_to_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()

def remove_white_bg(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    data  = image.getdata()
    image.putdata([(r,g,b,0) if r>200 and g>200 and b>200 else (r,g,b,a) for r,g,b,a in data])
    return image

def removebg_api(image: Image.Image, api_key: str) -> Image.Image | None:
    """Call remove.bg API to cleanly remove background from a clothing item."""
    try:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        resp = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            files={"image_file": ("image.png", buf, "image/png")},
            data={"size": "auto"},
            headers={"X-Api-Key": api_key},
            timeout=30
        )
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content)).convert("RGBA")
        return None
    except Exception:
        return None

def process_single_item(uploaded_file) -> Image.Image:
    img = Image.open(uploaded_file).convert("RGBA")
    if removebg_key:
        result = removebg_api(img, removebg_key)
        return result if result else remove_white_bg(img)
    return remove_white_bg(img)

# ══════════════════════════════════════════════
# AI FUNCTIONS
# ══════════════════════════════════════════════
def ai_generate_tags(image: Image.Image, category: str) -> list:
    defaults = {"Tops":["Mild","Spring","Casual"],"Bottoms":["Warm","Summer","Casual"],
                "Shoes":["All Weather","All Season","Casual"],"Accessories":["All Weather","All Season","Casual"]}
    if not gemini_client:
        return defaults.get(category, ["Casual","All Season","Everyday"])
    prompt = (
        f"Fashion stylist analyzing a {category} item.\n"
        f"Return ONLY a JSON list of exactly 3 strings: [weather_tag, season_tag, occasion_tag].\n"
        f"Weather: Hot, Warm, Mild, Cold, Rainy, All Weather\n"
        f"Season: Spring, Summer, Fall, Winter, All Season\n"
        f"Occasion: Casual, Work, Date Night, Wedding, BBQ, Gym, Mall, Going Out\n"
        f'Example: ["Warm","Summer","Casual"] — no other text.'
    )
    try:
        resp = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[types.Part.from_bytes(data=image_to_bytes(image), mime_type="image/png"), prompt]
        )
        cleaned = resp.text.strip().replace("```json","").replace("```","").strip()
        tags = json.loads(cleaned)
        if isinstance(tags, list) and len(tags) == 3:
            return tags
    except Exception:
        pass
    return defaults.get(category, ["Casual","All Season","Everyday"])


def ai_extract_outfit_items(image: Image.Image) -> list[dict] | None:
    """
    Given a full outfit photo, ask Gemini to identify each clothing item,
    its category, a short label, and suggested tags.
    Returns a list of dicts: {category, label, tags}
    """
    if not gemini_client:
        return None
    prompt = (
        "You are a fashion AI. Analyse this photo of a person wearing an outfit.\n"
        "Identify each visible clothing item (top, bottom, shoes, accessories).\n"
        "Return ONLY a JSON array — no markdown, no explanation. Each element:\n"
        '{"category": "Tops"|"Bottoms"|"Shoes"|"Accessories", '
        '"label": "short description e.g. White linen shirt", '
        '"tags": [weather_tag, season_tag, occasion_tag]}\n'
        "Weather options: Hot, Warm, Mild, Cold, Rainy, All Weather\n"
        "Season options: Spring, Summer, Fall, Winter, All Season\n"
        "Occasion options: Casual, Work, Date Night, Wedding, BBQ, Gym, Mall, Going Out\n"
        "Only include items you can clearly see. Max 4 items."
    )
    try:
        resp = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[types.Part.from_bytes(data=image_to_bytes(image), mime_type="image/png"), prompt]
        )
        cleaned = resp.text.strip().replace("```json","").replace("```","").strip()
        items = json.loads(cleaned)
        if isinstance(items, list):
            return items
    except Exception:
        pass
    return None


def ai_crop_item(full_image: Image.Image, item_label: str, category: str) -> Image.Image:
    """
    Use remove.bg to strip background from the full photo.
    We use the full outfit image as the base for each item since
    pixel-perfect cropping requires segmentation beyond free-tier tools.
    The stored image is the bg-removed outfit photo, labelled per item.
    """
    if removebg_key:
        result = removebg_api(full_image, removebg_key)
        if result:
            return result
    return remove_white_bg(full_image.copy())


def ai_suggest_outfit(top, bottom, shoes=None, occasion="Casual") -> str:
    if not gemini_client:
        return f"This combo works great for a {occasion} outing! Consider a simple accessory to finish the look. 💕"
    top_tags    = ", ".join(top["tags"])    if top    else "none"
    bottom_tags = ", ".join(bottom["tags"]) if bottom else "none"
    shoe_tags   = ", ".join(shoes["tags"])  if shoes  else "not selected"
    prompt = (
        f"Friendly personal stylist. Brief outfit review (2-3 warm sentences).\n"
        f"Top: {top_tags} | Bottom: {bottom_tags} | Shoes: {shoe_tags} | Occasion: {occasion}\n"
        f"Does it work? What to add or change?"
    )
    try:
        return gemini_client.models.generate_content(model="gemini-2.0-flash", contents=[prompt]).text.strip()
    except Exception:
        return "This outfit looks great! You're all set. 💕"


def ai_best_outfit(tops, bottoms, shoes_list, occasion) -> dict | None:
    if not tops or not bottoms:
        return None
    if not gemini_client:
        return {"top": random.choice(tops), "bottom": random.choice(bottoms),
                "shoes": random.choice(shoes_list) if shoes_list else None}
    td = "\n".join([f"Top {i}: {', '.join(t['tags'])}"    for i,t in enumerate(tops)])
    bd = "\n".join([f"Bottom {i}: {', '.join(b['tags'])}" for i,b in enumerate(bottoms)])
    sd = "\n".join([f"Shoes {i}: {', '.join(s['tags'])}"  for i,s in enumerate(shoes_list)]) if shoes_list else "None"
    prompt = (
        f"Pick the best outfit for: {occasion}\nTops:\n{td}\nBottoms:\n{bd}\nShoes:\n{sd}\n"
        f'Return ONLY JSON: {{"top":0,"bottom":1,"shoes":0}} — null for shoes if none. No extra text.'
    )
    try:
        resp    = gemini_client.models.generate_content(model="gemini-2.0-flash", contents=[prompt])
        cleaned = resp.text.strip().replace("```json","").replace("```","").strip()
        idx     = json.loads(cleaned)
        return {
            "top":    tops[idx.get("top",0)],
            "bottom": bottoms[idx.get("bottom",0)],
            "shoes":  shoes_list[idx["shoes"]] if shoes_list and idx.get("shoes") is not None else None
        }
    except Exception:
        return {"top": random.choice(tops), "bottom": random.choice(bottoms),
                "shoes": random.choice(shoes_list) if shoes_list else None}

# ══════════════════════════════════════════════
# GOOGLE SHEETS HELPERS
# ══════════════════════════════════════════════
SHEET_NAME = "VirtualClosetData"

def gs_get_or_create_sheet():
    if not gsheets_client:
        return None
    try:
        try:
            sh = gsheets_client.open(SHEET_NAME)
        except gspread.SpreadsheetNotFound:
            sh = gsheets_client.create(SHEET_NAME)
            sh.share(None, perm_type="anyone", role="reader")
        return sh
    except Exception:
        return None

def gs_save(profiles, saved_outfits):
    sh = gs_get_or_create_sheet()
    if not sh:
        return False
    try:
        # Serialize profiles — images as b64 strings, stored in a single cell as JSON
        payload = {
            "profiles":      profiles,
            "saved_outfits": saved_outfits
        }
        data_str = json.dumps(payload)
        try:
            ws = sh.worksheet("data")
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet("data", rows=2, cols=2)
        ws.update("A1", [[data_str]])
        st.session_state.gs_sheet_url = sh.url
        return True
    except Exception:
        return False

def gs_load():
    sh = gs_get_or_create_sheet()
    if not sh:
        return None
    try:
        ws      = sh.worksheet("data")
        raw     = ws.acell("A1").value
        payload = json.loads(raw)
        return payload
    except Exception:
        return None

# ══════════════════════════════════════════════
# JSON IMPORT / EXPORT
# ══════════════════════════════════════════════
def export_json() -> str:
    payload = {
        "profiles":      st.session_state.profiles,
        "saved_outfits": st.session_state.saved_outfits
    }
    return json.dumps(payload)

def import_json(raw: str):
    payload = json.loads(raw)
    st.session_state.profiles      = payload.get("profiles", st.session_state.profiles)
    st.session_state.saved_outfits = payload.get("saved_outfits", [])

# ══════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════
with st.sidebar:
    st.header("👤 Active Profile")
    current_user = st.radio("Who's styling?", PROFILE_KEYS)
    other_user   = PROFILE_KEYS[1] if current_user == PROFILE_KEYS[0] else PROFILE_KEYS[0]

    # ── Names ──
    st.divider()
    st.subheader("✏️ Profile Names")
    nc1, nc2 = st.columns(2)
    with nc1:
        n1 = st.text_input("Your name",     value=st.session_state.profiles["My Closet"]["name"],        key="nm1")
        st.session_state.profiles["My Closet"]["name"] = n1
    with nc2:
        n2 = st.text_input("Partner's name", value=st.session_state.profiles["Partner's Closet"]["name"], key="nm2")
        st.session_state.profiles["Partner's Closet"]["name"] = n2

    # ── Avatars — both visible at once ──
    st.divider()
    st.subheader("📸 Profile Photos")
    ac1, ac2 = st.columns(2)
    with ac1:
        me_name = st.session_state.profiles["My Closet"]["name"]
        st.caption(f"**{me_name}**")
        av_me = st.file_uploader(f"{me_name}'s photo", type=["png","jpg","jpeg"], key="av_me")
        if av_me:
            st.session_state.profiles["My Closet"]["avatar"] = image_to_base64(Image.open(av_me))
            st.success("Saved!")
        if st.session_state.profiles["My Closet"]["avatar"]:
            st.image(base64_to_image(st.session_state.profiles["My Closet"]["avatar"]), use_container_width=True)
    with ac2:
        partner_name = st.session_state.profiles["Partner's Closet"]["name"]
        st.caption(f"**{partner_name}**")
        av_p = st.file_uploader(f"{partner_name}'s photo", type=["png","jpg","jpeg"], key="av_partner")
        if av_p:
            st.session_state.profiles["Partner's Closet"]["avatar"] = image_to_base64(Image.open(av_p))
            st.success("Saved!")
        if st.session_state.profiles["Partner's Closet"]["avatar"]:
            st.image(base64_to_image(st.session_state.profiles["Partner's Closet"]["avatar"]), use_container_width=True)

    # ── Add clothes ──
    st.divider()
    st.subheader("➕ Add Clothes")
    upload_mode   = st.radio("Upload mode", ["Single item photo", "Full outfit photo (AI extracts items)"])
    upload_target = st.selectbox("Add to whose closet?", [current_user, other_user])

    if upload_mode == "Single item photo":
        cat       = st.selectbox("Category", CATEGORIES)
        item_file = st.file_uploader("Photo of item", type=["png","jpg","jpeg"], key="item_upload")
        if st.button("✨ Save Item") and item_file:
            with st.spinner("Processing & tagging..."):
                img  = process_single_item(item_file)
                tags = ai_generate_tags(img, cat)
                b64  = image_to_base64(img)
            st.session_state.profiles[upload_target]["closet"][cat].append(
                {"image_b64": b64, "tags": tags, "label": ""}
            )
            st.success(f"Added to {cat}! Tags: {', '.join(tags)}")
            st.rerun()

    else:  # Full outfit photo
        if not gemini_client:
            st.warning("Gemini API key required for outfit extraction. Add GOOGLE_API_KEY to Streamlit secrets.")
        outfit_file = st.file_uploader("Photo wearing the outfit", type=["png","jpg","jpeg"], key="outfit_upload")
        if st.button("🔍 Extract & Save Items") and outfit_file:
            with st.spinner("Analysing outfit with AI..."):
                full_img  = Image.open(outfit_file).convert("RGBA")
                items     = ai_extract_outfit_items(full_img)
            if not items:
                st.error("Couldn't identify items. Try a clearer photo with good lighting.")
            else:
                with st.spinner(f"Saving {len(items)} items to your closet..."):
                    saved_count = 0
                    for item in items:
                        cat_   = item.get("category", "Tops")
                        label  = item.get("label", "")
                        tags   = item.get("tags", ["Casual","All Season","Everyday"])
                        if cat_ not in CATEGORIES:
                            cat_ = "Tops"
                        # Use remove.bg on the full photo for best bg removal
                        cleaned = ai_crop_item(full_img, label, cat_)
                        b64     = image_to_base64(cleaned)
                        st.session_state.profiles[upload_target]["closet"][cat_].append(
                            {"image_b64": b64, "tags": tags, "label": label}
                        )
                        saved_count += 1
                st.success(f"Saved {saved_count} items! Check each category in your closet.")
                st.rerun()

    if not gemini_client:
        st.caption("💡 Add GOOGLE_API_KEY to Streamlit secrets for AI features.")
    if not removebg_key:
        st.caption("💡 Add REMOVEBG_API_KEY for clean background removal.")

    # ── Closet counts ──
    st.divider()
    st.caption(f"**{st.session_state.profiles[current_user]['name']}'s closet:**")
    for c, items in st.session_state.profiles[current_user]["closet"].items():
        st.caption(f"  {c}: {len(items)}")

    # ── Save / Load ──
    st.divider()
    st.subheader("💾 Save & Load Closet")

    # Google Sheets
    if gsheets_client:
        gsc1, gsc2 = st.columns(2)
        if gsc1.button("☁️ Save to Sheets"):
            with st.spinner("Saving..."):
                ok = gs_save(st.session_state.profiles, st.session_state.saved_outfits)
            if ok:
                st.success("Saved to Google Sheets!")
                if st.session_state.gs_sheet_url:
                    st.caption(f"[Open sheet]({st.session_state.gs_sheet_url})")
            else:
                st.error("Save failed. Check your GSHEETS_CREDENTIALS secret.")
        if gsc2.button("☁️ Load from Sheets"):
            with st.spinner("Loading..."):
                payload = gs_load()
            if payload:
                st.session_state.profiles      = payload.get("profiles", st.session_state.profiles)
                st.session_state.saved_outfits = payload.get("saved_outfits", [])
                st.success("Loaded from Google Sheets!")
                st.rerun()
            else:
                st.error("Nothing found in Sheets yet.")
    else:
        st.caption("Add GSHEETS_CREDENTIALS to Streamlit secrets to enable cloud save.")

    # JSON backup
    json_str = export_json()
    st.download_button(
        label="⬇️ Download backup (.json)",
        data=json_str,
        file_name="my_closet_backup.json",
        mime="application/json"
    )
    restore_file = st.file_uploader("⬆️ Restore from backup", type=["json"], key="restore_upload")
    if restore_file and st.button("📂 Load Backup"):
        try:
            import_json(restore_file.read().decode())
            st.success("Closet restored!")
            st.rerun()
        except Exception:
            st.error("Invalid backup file.")

# ══════════════════════════════════════════════
# MAIN AREA
# ══════════════════════════════════════════════
cur_name     = st.session_state.profiles[current_user]["name"]
other_name   = st.session_state.profiles[other_user]["name"]

st.subheader(f"👗 {cur_name}'s Dressing Room")

borrow = st.checkbox(f"🔄 Also include {other_name}'s clothes", value=False)

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
        if weather_filter != "All Weather" and weather_filter.lower() not in tl: continue
        if season_filter  != "All Season"  and season_filter.lower()  not in tl: continue
        filtered.append(item)
    return filtered

tops       = get_items("Tops")
bottoms    = get_items("Bottoms")
shoes_list = get_items("Shoes")

if tops       and st.session_state.top_index    >= len(tops):       st.session_state.top_index    = 0
if bottoms    and st.session_state.bottom_index >= len(bottoms):    st.session_state.bottom_index = 0
if shoes_list and st.session_state.shoe_index   >= len(shoes_list): st.session_state.shoe_index   = 0

st.divider()

avatar_col, outfit_col = st.columns([4, 6])

with avatar_col:
    st.subheader(f"📸 {cur_name}'s Photo")
    if st.session_state.profiles[current_user]["avatar"]:
        st.image(base64_to_image(st.session_state.profiles[current_user]["avatar"]), use_container_width=True)
    else:
        st.info(f"Upload {cur_name}'s photo in the sidebar.")

with outfit_col:
    st.subheader("✨ Mix & Match")

    if not tops and not bottoms:
        st.warning("No items match your filters. Add clothes in the sidebar to get started!")
    else:
        b1, b2, b3, b4 = st.columns(4)
        if tops       and b1.button("👚 Next Top"):    st.session_state.top_index    = (st.session_state.top_index    + 1) % len(tops)
        if bottoms    and b2.button("👖 Next Bottom"): st.session_state.bottom_index = (st.session_state.bottom_index + 1) % len(bottoms)
        if shoes_list and b3.button("👟 Next Shoes"):  st.session_state.shoe_index   = (st.session_state.shoe_index   + 1) % len(shoes_list)
        if b4.button("🎲 Shuffle"):
            if tops:       st.session_state.top_index    = random.randint(0, len(tops)-1)
            if bottoms:    st.session_state.bottom_index = random.randint(0, len(bottoms)-1)
            if shoes_list: st.session_state.shoe_index   = random.randint(0, len(shoes_list)-1)

        current_top    = tops[st.session_state.top_index]        if tops       else None
        current_bottom = bottoms[st.session_state.bottom_index]  if bottoms    else None
        current_shoes  = shoes_list[st.session_state.shoe_index] if shoes_list else None

        ic1, ic2, ic3 = st.columns(3)
        for col, item, caption in [
            (ic1, current_top,    "Top"),
            (ic2, current_bottom, "Bottom"),
            (ic3, current_shoes,  "Shoes")
        ]:
            if item:
                with col:
                    label = item.get("label", "")
                    cap   = f"{caption}: {label}" if label else caption
                    st.image(base64_to_image(item["image_b64"]), caption=cap, use_container_width=True)
                    st.caption(" · ".join(item["tags"]))

        st.divider()

        ac1, ac2, ac3 = st.columns(3)

        if ac1.button("💬 AI Outfit Tip"):
            with st.spinner("Asking your stylist..."):
                st.session_state.ai_suggestion = ai_suggest_outfit(
                    current_top, current_bottom, current_shoes, occasion_filter
                )

        if ac2.button("🎯 AI Best Pick"):
            with st.spinner("Finding the best combo..."):
                result = ai_best_outfit(tops, bottoms, shoes_list, occasion_filter)
                if result:
                    if result["top"]    in tops:       st.session_state.top_index    = tops.index(result["top"])
                    if result["bottom"] in bottoms:    st.session_state.bottom_index = bottoms.index(result["bottom"])
                    if result.get("shoes") and result["shoes"] in shoes_list:
                        st.session_state.shoe_index = shoes_list.index(result["shoes"])
                    st.session_state.ai_suggestion = "🎯 AI picked this outfit for you!"
            st.rerun()

        if ac3.button("❤️ Save Outfit"):
            st.session_state.saved_outfits.append({
                "user":        cur_name,
                "occasion":    occasion_filter,
                "top_tags":    current_top["tags"]    if current_top    else [],
                "bottom_tags": current_bottom["tags"] if current_bottom else [],
                "shoe_tags":   current_shoes["tags"]  if current_shoes  else [],
                "top_label":    current_top.get("label","")    if current_top    else "",
                "bottom_label": current_bottom.get("label","") if current_bottom else "",
                "shoe_label":   current_shoes.get("label","")  if current_shoes  else "",
            })
            st.toast("Outfit saved! ❤️")

        if st.session_state.ai_suggestion:
            st.info(f"💬 {st.session_state.ai_suggestion}")

# ── Saved outfits ──
if st.session_state.saved_outfits:
    st.divider()
    st.subheader("❤️ Saved Outfits")
    for i, outfit in enumerate(reversed(st.session_state.saved_outfits)):
        n = len(st.session_state.saved_outfits) - i
        with st.expander(f"Outfit {n} — {outfit['occasion']} ({outfit['user']})"):
            tl = outfit.get("top_label","")    or ", ".join(outfit["top_tags"])
            bl = outfit.get("bottom_label","") or ", ".join(outfit["bottom_tags"])
            sl = outfit.get("shoe_label","")   or ", ".join(outfit["shoe_tags"])
            st.write(f"**Top:** {tl or 'N/A'}")
            st.write(f"**Bottom:** {bl or 'N/A'}")
            st.write(f"**Shoes:** {sl or 'N/A'}")
