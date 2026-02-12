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
# Öncelik: Streamlit Cloud secrets
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", None)

# Eğer istersen lokal geliştirme için ortam değişkenini açabilirsin:
# if not GEMINI_API_KEY:
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY tanımlı değil. "
        "Lokal için ortam değişkenine, Cloud için Secrets'e eklemelisin."
    )

client = genai.Client(api_key=GEMINI_API_KEY)

st.set_page_config(page_title="Gemini Lingerie Studio", layout="wide")

# =========================
#  BASİT LOGIN / ŞİFRE KORUMASI
# =========================
APP_PASSWORD = st.secrets.get("APP_PASSWORD", None) or os.getenv("APP_PASSWORD", "")

if not APP_PASSWORD:
    raise RuntimeError("APP_PASSWORD tanımlı değil. Secrets'e eklemelisin.")

# # Session state'te login durumu saklanır
if "auth_ok" not in st.session_state:
    st.session_state["auth_ok"] = False

 # Eğer henüz login değilse:
if not st.session_state["auth_ok"]:
    st.title("🔒 G Lingerie Studio – Yetkili Erişim")

    pwd = st.text_input("Erişim şifresi", type="password")
    login_button = st.button("Giriş yap")

    if login_button:
        if pwd == APP_PASSWORD:
            st.session_state["auth_ok"] = True
            st.success("Giriş başarılı! Yükleniyor...")
            st.rerun()   # SAYFAYI TEMİZ BİR ŞEKİLDE YENİDEN AÇAR
        else:
            st.error("Yanlış şifre. Lütfen tekrar deneyin.")

    st.stop()  # Login başarısız veya daha giriş yapılmamış → uygulamanın devamı render edilmez


# =========================
#  MEMORY / BAĞLAM
# =========================
if "history" not in st.session_state:
    st.session_state["history"] = []  # her eleman bir string: "Ürün: ..., Ayarlar: ..."


# =========================
#  PROMPT BUILDER
# =========================

SYSTEM_PROMPT = """
You are a professional fashion image generation system specialized in e-commerce product visualization.

CRITICAL INSTRUCTIONS – MUST BE FOLLOWED:

1. REFERENCE IMAGE HANDLING
- Product reference images may include a human model.
- From product reference images, you must extract and use ONLY the garment itself:
  garment design, color, fabric, texture, and construction details.
- Any human model present in product reference images MUST be completely ignored.
- Do NOT reuse or imitate the face, body, pose, hairstyle, skin tone, or identity of the model shown.

2. MODEL REFERENCE HANDLING
- If separate model reference images are provided, use them ONLY as a general reference
  for body proportions, pose direction, and viewing angle.
- Do NOT copy or replicate the exact identity.

3. STRICT SEPARATION RULE
- The garment and the model are two fully independent entities.
- Garment information comes ONLY from product reference images and text.
- Model appearance comes ONLY from model reference images (if provided) and prompt instructions.

4. MODEL GENERATION RULE
- Always generate a DIFFERENT male model wearing the same garment.
- Never reuse the same model identity across generations unless explicitly instructed.

5. OUTPUT STYLE
- Professional e-commerce fashion catalog photography
- Neutral, non-sexualized pose
- Product-focused composition
- Accurate garment representation
- The mannequins should stand vertically in the image
"""

def pil_to_part(img: Image.Image) -> types.Part:
    """PIL Image -> Gemini inline image part"""
    buf = BytesIO()
    # PNG güvenli, şeffaflık vs. için iyi
    img.convert("RGB").save(buf, format="PNG")
    return types.Part(
        inline_data=types.Blob(
            mime_type="image/png",
            data=buf.getvalue()
        )
    )

def build_prompt(product_text, shot_type, scene_style, extra_notes):
    parts = []

    # Kadraj
    if shot_type == "Full body":
        parts.append(
            "full body fashion shot of a male model, standing naturally, "
            "entire outfit visible from head to toe, head and feet fully in frame, balanced proportions, "
            "catalog-style composition"
        )

    elif shot_type == "Upper body":
        parts.append(
            "upper body fashion shot of a male model, framed from the top of the head to the waist, full head completely in frame"
            "clear focus on the top garment, natural posture, clean and professional "
            "e-commerce composition"
        )

    elif shot_type == "Lower body":
        parts.append(
            "lower body fashion shot of a male model, framed from the waist down to the feet, "
            "upper body not visible, full legs and feet completely in frame, clear focus on the bottom garment, "
            "accurate fit and fabric details, clean catalog-style composition"
        )

    #Side/Yön
    if side_view == "Ön":
        parts.append(
            "front-facing view of the male model, facing the camera directly, "
            "clear and unobstructed view of the garment, symmetrical presentation, "
            "ideal for e-commerce product display, neutral and natural posture"
    )

    elif side_view == "Sol çapraz":
        parts.append(
            "three-quarter angle view from the left side, male model slightly turned, "
            "showing both front and side of the garment, natural relaxed posture, "
            "enhances depth and fabric drape, suitable for lingerie and sleepwear catalog"
    )


    elif side_view == "Arka":
        parts.append(
            "back view of the male model, facing away from the camera, "
            "clear visibility of the back design of the garment, straps, seams, and fit, "
            "neutral posture, professional catalog presentation"
    )

    # Ortam
    if scene_style == "E-commerce studio":
        parts.append(
            "in a professional e-commerce studio, clean white seamless background, "
            "even softbox lighting, no props"
        )
    elif scene_style == "Lifestyle (yatak odası)":
        parts.append(
            "in a cozy modern bedroom, soft natural window light, neutral colors"
        )
    elif scene_style == "Lifestyle (spor salonu)":
        parts.append(
            "in a bright modern gym interior, clean and minimal environment"
        )
    else:
        parts.append(
            "in a minimal, softly lit neutral background"
        )

    # Ürün açıklaması
    if product_text:
        parts.append(
            f"the model is wearing: {product_text}. "
            "The lingerie must be clearly visible, accurate to the description, "
            "and realistically fitted to the body."
        )

    # Ek notlar
    if extra_notes:
        parts.append(extra_notes)

    # Genel stil – iç giyim katalog dili
    parts.append(
        "high-end lingerie catalog photography, realistic skin texture, natural body shape, "
        "accurate fabric details, no heavy retouch, soft professional lighting, "
        "shot on a high-resolution camera."
    )

    return ", ".join(parts)


def history_entry(product_text,shot_type,side_view, scene_style, extra_notes):
    return (
        f"[SHOT={shot_type}, SCENE={scene_style}] "
        f"PRODUCT: {product_text or '-'} "
        f"EXTRA: {extra_notes or '-'}"
    )


def decode_gemini_image(part):
    """Gemini image part → PIL Image"""
    blob = part.inline_data
    data = blob.data

    # Bazı sürümlerde data zaten bytes, bazılarında base64 string olabiliyor.
    if isinstance(data, bytes):
        image_bytes = data
    else:
        image_bytes = base64.b64decode(data)

    return Image.open(BytesIO(image_bytes))


def part_to_streamlit_image(part):
    img = decode_gemini_image(part)
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


# =========================
#  ANA UI
# =========================
st.title("👗 G Lingerie Studio (Gemini + Memory)")

with st.sidebar:
    st.header("⚙️ Ayarlar")

    model_name = st.selectbox(
        "Model",
        [
            "gemini-2.5-flash-image",
            "gemini-3-pro-image-preview",  # hesabında bu model yoksa flash kullan
        ],
    )

    shot_type = st.selectbox(
        "Kadraj / shot type",
        ["Full body", "Upper body", "Lower body"],
    )

    side_view = st.selectbox(
        "Side / Yön",
        ["Ön", "Sol çapraz", "Arka"],
    )

    scene_style = st.selectbox(
        "Sahne / ortam",
        [
            "E-commerce studio",
            "Lifestyle (yatak odası)",
            "Lifestyle (spor salonu)",
            "Minimal (nötr arka plan)",
        ],
    )

    aspect_ratio = st.selectbox(
        "Görsel oranı (şimdilik sadece prompt'ta kullanılıyor)",
        ["1:1","4:5", "3:4", "9:16", "16:9","5:6","10:13"],
    )

    resolution = st.selectbox(
        "Çözünürlük ",
        ["1K", "2K"],
    )

    use_context = st.checkbox(
        "Önceki istekleri bağlam olarak kullan",
        value=True,
    )

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
        "Ürün görselleri (1–3 adet)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )

with col2:
    model_files = st.file_uploader(
        "Manken / karakter görselleri (opsiyonel, max 5)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )

extra_notes = st.text_area(
    "3️⃣ Ek styling / poz notları (opsiyonel)",
    placeholder="Örn: model kamera karşısında hafif gülümser, yumuşak stüdyo ışığı, fazla retouch yok...",
)

generate_btn = st.button("🚀 Görsel Üret")


# =========================
#  HISTORY GÖRÜNÜMÜ
# =========================
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
            # 1) Bu isteği history'e ekle
            entry = history_entry(product_text, shot_type,side_view,scene_style, extra_notes)
            st.session_state["history"].append(entry)

            # 2) Prompt'u hazırla
            base_prompt = build_prompt(product_text, shot_type, scene_style, extra_notes)
            base_prompt += f", aspect ratio {aspect_ratio}, target resolution {resolution}."

            # --- Görselleri oku (PIL) ---
            pil_product_images = [Image.open(f) for f in (product_files or [])[:3]]
            pil_model_images   = [Image.open(f) for f in (model_files or [])[:5]]
            # 3) contents dizisini hazırlayalım
            contents = []
            
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text="SYSTEM INSTRUCTIONS (follow strictly):\n" + SYSTEM_PROMPT)]
                    )
                )
            
            # 2) Geçmiş bağlam (opsiyonel)
            if use_context:
                for h in st.session_state["history"][:-1]:
                    contents.append(
                        types.Content(
                            role="user",
                            parts=[types.Part(text=f"Previous request preferences (for consistency, do not repeat): {h}")]
                            )
                        )
                    
                    
            # 3) Asıl kullanıcı promptu
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text=base_prompt)]
                    )
                )
            
            
            # 4) Ürün görselleri (sadece ürün detayları için)
            if pil_product_images:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text="PRODUCT REFERENCE IMAGES (use ONLY garment details; ignore any human model in these images):")]
                        )
                    )
                for img in pil_product_images:
                    contents.append(types.Content(role="user", parts=[pil_to_part(img)]))
                    
                    
            # 5) Manken görselleri (sadece manken referansı için)
            if pil_model_images:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text="MODEL REFERENCE IMAGES (use ONLY as body/pose/angle reference; do not copy identity):")]
                        )
                    )
                for img in pil_model_images:
                    contents.append(types.Content(role="user", parts=[pil_to_part(img)]))
        

            # 4) Gemini'yi çağır
            with st.spinner("Gemini ile görsel üretiliyor..."):
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                )
                
                
            if pil_product_images:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text="PRODUCT REFERENCE IMAGES (use ONLY garment details; ignore any human model in these images):")]
                            + [pil_to_part(img) for img in pil_product_images]
                            )
                    )

            if pil_model_images:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text="MODEL REFERENCE IMAGES (use ONLY as body/pose/angle reference; do not copy identity):")]
                        + [pil_to_part(img) for img in pil_model_images]
                        )
                    )


            # 5) Görselleri çek (yeni SDK: candidates[*].content.parts)
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
                st.error("Gemini görsel döndürmedi. Güvenlik filtresi veya başka bir hata olabilir.")
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
