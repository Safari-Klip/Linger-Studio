import os
from io import BytesIO
import base64

import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

# =========================
#  GEMINI API AYARI
# =========================
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", None)

# Lokal geliştirme için istersen aç:
# if not GEMINI_API_KEY:
#     _API_KEY = os.getenv("_API_KEY", "")

if not _API_KEY:
    raise RuntimeError(
        "_API_KEY tanımlı değil. "
        "Lokal için ortam değişkenine, Cloud için Secrets'e eklemelisin."
    )

client = genai.Client(api_key=_API_KEY)

st.set_page_config(page_title=" Lingerie Studio", layout="wide")

# =========================
#  BASİT LOGIN / ŞİFRE KORUMASI
# =========================
APP_PASSWORD = st.secrets.get("APP_PASSWORD", None) or os.getenv("APP_PASSWORD", "")
if not APP_PASSWORD:
    raise RuntimeError("APP_PASSWORD tanımlı değil. Secrets'e eklemelisin.")

if "auth_ok" not in st.session_state:
    st.session_state["auth_ok"] = False

if not st.session_state["auth_ok"]:
    st.title("🔒 G Lingerie Studio – Yetkili Erişim")

    pwd = st.text_input("Erişim şifresi", type="password")
    login_button = st.button("Giriş yap")

    if login_button:
        if pwd == APP_PASSWORD:
            st.session_state["auth_ok"] = True
            st.success("Giriş başarılı! Yükleniyor...")
            st.rerun()
        else:
            st.error("Yanlış şifre. Lütfen tekrar deneyin.")

    st.stop()

# =========================
#  SYSTEM PROMPT (ÜRÜN vs MANKEN AYRIMI)
# =========================
SYSTEM_PROMPT = """
You are a professional fashion image generation system specialized in e-commerce product visualization.

CRITICAL INSTRUCTIONS – MUST BE FOLLOWED:

1. REFERENCE IMAGE HANDLING (PRODUCT IMAGES)
- Product reference images may include a human model.
- From product reference images, you must extract and use ONLY the garment itself:
  garment design, color, fabric, texture, and construction details.
- Any human model present in product reference images MUST be completely ignored.
- Do NOT reuse or imitate the face, body, pose, hairstyle, skin tone, or identity of any model shown in product reference images.

2. MODEL REFERENCE HANDLING (MODEL IMAGES)
- If separate model reference images are provided, use them ONLY as a general reference for:
  body proportions, pose direction, and viewing angle.
- Do NOT replicate the exact identity, face, or personal attributes unless explicitly requested.
- Prioritize creating a new identity over similarity to any reference.

3. STRICT SEPARATION RULE
- The garment and the model must be treated as two fully independent entities.
- Garment information comes ONLY from product reference images and text.
- Model appearance guidance comes ONLY from model reference images (if provided) and prompt instructions.

4. MODEL GENERATION RULE
- Always generate a DIFFERENT female model wearing the same garment.
- Never reuse the same model identity across generations unless explicitly instructed.

5. OUTPUT STYLE REQUIREMENTS
- Professional e-commerce fashion catalog photography
- Neutral, non-sexualized pose
- Product-focused composition
- Realistic proportions and fit
- Accurate garment representation without creative alterations
"""

# =========================
#  MEMORY / BAĞLAM
# =========================
if "history" not in st.session_state:
    st.session_state["history"] = []

# =========================
#  PROMPT BUILDER
# =========================
def build_prompt(product_text, shot_type, side_view, scene_style, extra_notes):
    parts = []

    # Kadraj
    if shot_type == "Full body":
        parts.append(
            "full body fashion shot of a female model, standing naturally, "
            "entire outfit visible from head to toe, balanced proportions, catalog-style composition"
        )
    elif shot_type == "Upper body":
        parts.append(
            "upper body fashion shot of a female model, framed from shoulders to waist, "
            "clear focus on the top garment, natural posture, clean professional e-commerce composition"
        )
    else:  # Lower body
        parts.append(
            "lower body fashion shot of a female model, framed from waist to mid-thigh or knees, "
            "clear focus on the bottom garment, accurate fit and fabric details, clean catalog composition"
        )

    # Side / Yön
    if side_view == "Ön":
        parts.append(
            "front-facing view, facing the camera directly, clear unobstructed view of the garment, "
            "symmetrical presentation, neutral natural posture"
        )
    elif side_view == "Sol çapraz":
        parts.append(
            "three-quarter angle view from the left, slightly turned, showing both front and side, "
            "natural relaxed posture, shows fabric drape and fit clearly"
        )
    else:  # Arka
        parts.append(
            "back view, facing away from the camera, clear visibility of back design, straps, seams, and fit, "
            "neutral professional catalog presentation"
        )

    # Ortam
    if scene_style == "E-commerce studio":
        parts.append(
            "professional e-commerce studio, clean white seamless background, soft even lighting, no props"
        )
    elif scene_style == "Lifestyle (yatak odası)":
        parts.append("cozy modern bedroom setting, soft natural window light, neutral colors")
    elif scene_style == "Lifestyle (spor salonu)":
        parts.append("bright modern gym interior, clean minimal environment")
    else:
        parts.append("minimal neutral background with soft professional lighting")

    # Ürün açıklaması
    if product_text:
        parts.append(
            f"the model is wearing: {product_text}. "
            "The garment must be clearly visible, accurate to the description and reference, "
            "and realistically fitted."
        )

    # Ek notlar
    if extra_notes:
        parts.append(extra_notes)

    # Genel stil
    parts.append(
        "high-end lingerie and sleepwear catalog photography, realistic skin texture, natural body shape, "
        "accurate fabric details, no heavy retouch, product-focused, commercial look"
    )

    return ", ".join(parts)


def history_entry(product_text, shot_type, side_view, scene_style, extra_notes):
    return (
        f"[SHOT={shot_type}, SIDE={side_view}, SCENE={scene_style}] "
        f"PRODUCT: {product_text or '-'} "
        f"EXTRA: {extra_notes or '-'}"
    )


def decode__image(part):
    blob = part.inline_data
    data = blob.data
    if isinstance(data, bytes):
        image_bytes = data
    else:
        image_bytes = base64.b64decode(data)
    return Image.open(BytesIO(image_bytes))


def part_to_streamlit_image(part):
    img = decode__image(part)
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


# =========================
#  ANA UI
# =========================
st.title("👗 G Lingerie Studio ( + Memory)")

with st.sidebar:
    st.header("⚙️ Ayarlar")

    model_name = st.selectbox(
        "Model",
        [
            "-2.5-flash-image",
            "gemini-3-pro-image-preview", 
            # 3.x pro image sende yoksa hata verir. İstersen kaldır.
            # "gemini-3-pro-image-preview",
        ],
    )

    shot_type = st.selectbox("Kadraj / shot type", ["Full body", "Upper body", "Lower body"])
    side_view = st.selectbox("Side / Yön", ["Ön", "Sol çapraz", "Arka"])

    scene_style = st.selectbox(
        "Sahne / ortam",
        ["E-commerce studio", "Lifestyle (yatak odası)", "Lifestyle (spor salonu)", "Minimal (nötr arka plan)"],
    )

    aspect_ratio = st.selectbox("Görsel oranı (prompt)", ["1:1", "4:5", "3:4", "9:16", "16:9", "5:6", "10:13"])
    resolution = st.selectbox("Çözünürlük (prompt)", ["1K", "2K"])

    use_context = st.checkbox("Önceki istekleri bağlam olarak kullan", value=True)

    st.markdown("---")
    if st.button("🧹 Bağlamı sıfırla (history temizle)"):
        st.session_state["history"] = []
        st.success("Bağlam temizlendi.")

st.subheader("1️⃣ Ürün Bilgisi")
product_text = st.text_area(
    "Ürünü kısaca tanımla (marka, model, renk, özellikler)",
    placeholder="Örn: Chantelle SoftStretch Power derin V yaka sütyen, bej, dikişsiz, tam toparlayıcı...",
)

st.subheader("2️⃣ Referans Görseller")
col1, col2 = st.columns(2)

with col1:
    product_files = st.file_uploader(
        "Ürün görselleri (1–3 adet) — mümkünse cut-out/ürün odaklı",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )

with col2:
    model_files = st.file_uploader(
        "Manken / karakter görselleri (opsiyonel, max 5) — sadece manken referansı",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )

extra_notes = st.text_area(
    "3️⃣ Ek styling / poz notları (opsiyonel)",
    placeholder="Örn: soft studio light, neutral expression, arms relaxed...",
)

generate_btn = st.button("🚀 Görsel Üret")

with st.expander("🧠 Konuşma bağlamı / önceki istekler", expanded=False):
    st.write(f"Toplam kayıt sayısı: {len(st.session_state['history'])}")
    if not st.session_state["history"]:
        st.write("Henüz kayıtlı bağlam yok.")
    else:
        for i, h in enumerate(st.session_state["history"], start=1):
            st.markdown(f"**{i}.** {h}")

# =========================
#  GEMINI ÇAĞRISI
# =========================
if generate_btn:
    if not product_text and not product_files:
        st.error("En az bir ürün açıklaması veya ürün görseli yüklemelisin.")
    else:
        try:
            entry = history_entry(product_text, shot_type, side_view, scene_style, extra_notes)
            st.session_state["history"].append(entry)

            base_prompt = build_prompt(product_text, shot_type, side_view, scene_style, extra_notes)
            base_prompt += f", aspect ratio {aspect_ratio}, target resolution {resolution}."

            # Görselleri oku
            pil_product_images = [Image.open(f) for f in (product_files or [])[:3]]
            pil_model_images = [Image.open(f) for f in (model_files or [])[:5]]

            # =========================
            #  CONTENTS: SYSTEM + USER + IMAGES (ROL AYRIMI)
            # =========================
            contents = []

            # 1) System prompt
            contents.append(
                types.Content(
                    role="system",
                    parts=[types.Part(text=SYSTEM_PROMPT)]
                )
            )

            # 2) Context (opsiyonel)
            if use_context:
                for h in st.session_state["history"][:-1]:
                    contents.append(
                        types.Content(
                            role="user",
                            parts=[types.Part(text=f"Previous request preferences (for consistency, do not repeat): {h}")]
                        )
                    )

            # 3) User prompt
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text=base_prompt)]
                )
            )

            # 4) Görselleri role-based anlat (metin + görsel)
            if pil_product_images:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text="PRODUCT REFERENCE IMAGES (use ONLY the garment details; ignore any human model):")]
                    )
                )
                for img in pil_product_images:
                    contents.append(types.Content(role="user", parts=[img]))

            if pil_model_images:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text="MODEL REFERENCE IMAGES (use ONLY for general body/pose/angle reference; do not copy identity):")]
                    )
                )
                for img in pil_model_images:
                    contents.append(types.Content(role="user", parts=[img]))

            # 5) Çağır
            with st.spinner("Gemini ile görsel üretiliyor..."):
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                )

            # 6) Görselleri çek
            all_parts = []
            candidates = getattr(response, "candidates", None)
            if candidates:
                for cand in candidates:
                    content = getattr(cand, "content", None)
                    parts = getattr(content, "parts", None)
                    if parts:
                        all_parts.extend(parts)

            image_parts = [
                p for p in all_parts
                if getattr(p, "inline_data", None) is not None
                and getattr(p.inline_data, "mime_type", "").startswith("image/")
            ]

            if not image_parts:
                st.error("Gemini görsel döndürmedi. Güvenlik filtresi veya model uyumsuzluğu olabilir.")
            else:
                st.success("Görseller üretildi ✅")

                cols = st.columns(len(image_parts))
                for idx, (col, part) in enumerate(zip(cols, image_parts)):
                    with col:
                        buf = part_to_streamlit_image(part)
                        st.image(buf, caption=f"Sonuç #{idx+1}")
                        st.download_button(
                            label="🔽 İndir",
                            data=buf,
                            file_name=f"gemini_output_{idx+1}.png",
                            mime="image/png",
                        )

        except Exception as e:
            st.error(f"Hata oluştu: {e}")
