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

def get_system_prompt(gender_en):
    return f"""
You are a professional fashion image generation system specialized in e-commerce product visualization.

CRITICAL INSTRUCTIONS – MUST BE FOLLOWED:

1. PRODUCT SOURCE PRIORITY RULE
- Product reference images are the primary source for garment shape, fit, silhouette, seams, buttons, pockets, collar, sleeves, waistband, print placement, fabric texture and construction details.
- Written product instructions are the primary source for exact color, Pantone code, HEX code, fabric name, unclear details and corrections.
- If the written prompt includes a color name, Pantone code, HEX code, fabric type or correction, it OVERRIDES the visual color or unclear detail in the reference image.
- If no written correction is provided, reproduce the garment exactly as shown in the product image.
- Do not ignore written instructions.
- Do not invent missing product details.

2. PRODUCT ACCURACY RULE
- The garment shown in the product reference image is the source of truth.
- Do not redesign the garment.
- Do not modify print pattern, artwork, embroidery, lace placement, stitching, buttons, pockets, collar shape, sleeve length, waistband, hem, piping, cuffs, fabric texture or garment proportions.
- Product accuracy is more important than model beauty.

3. PAJAMA / SLEEPWEAR RULE
- For pajamas and sleepwear, preserve the exact set structure: top, bottom, collar, sleeve length, button count, pocket position, piping, cuffs and waistband.
- The print pattern must remain identical to the reference image.
- Do not reinterpret, simplify, recreate, redraw or invent new pattern elements.

4. REFERENCE IMAGE HANDLING
- Product reference images may include a human model.
- From product reference images, use ONLY the garment itself.
- Any human model present in product reference images MUST be completely ignored.
- Do NOT reuse or imitate the face, body, pose, hairstyle, skin tone, or identity of the model shown.

5. MODEL REFERENCE HANDLING
- If separate model reference images are provided, use them ONLY as a general reference for body proportions, pose direction and viewing angle.
- Do NOT copy or replicate the exact identity.

6. STRICT SEPARATION RULE
- The garment and the model are two fully independent entities.
- Garment information comes ONLY from product reference images and written product text.
- Model appearance comes ONLY from model reference images, if provided, and prompt instructions.

7. MODEL GENERATION RULE
- Always generate a DIFFERENT {gender_en} model wearing the same garment.
- Never reuse the same model identity across generations unless explicitly instructed.

8. OUTPUT STYLE
- Professional e-commerce fashion catalog photography.
- Neutral, non-sexualized pose.
- Product-focused composition.
- Accurate garment representation.
- The model should stand vertically in the image.
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

def build_prompt(product_text, shot_type, side_view, scene_style, extra_notes, gender_en):
    parts = []

    # Kadraj
    if shot_type == "Full body":
        parts.append(
            f"full body fashion shot of a {gender_en} model, standing naturally, "
            "entire outfit visible from head to toe, eyes,head and feet fully in frame, balanced proportions, "
            "catalog-style composition"
        )

    elif shot_type == "Upper body":
        parts.append(
            f"upper body fashion shot of a {gender_en} model, framed from the top of the head to the waist, full head completely in frame, "
            "clear focus on the top garment, natural posture, clean and professional "
            "e-commerce composition"
        )

    elif shot_type == "Lower body":
        parts.append(
            f"lower body fashion shot of a {gender_en} model, framed from the waist down to the feet, "
            "upper body not visible, full legs and feet completely in frame, clear focus on the bottom garment, "
            "accurate fit and fabric details, clean catalog-style composition"
        )

    # Side/Yön
    if side_view == "Ön":
        parts.append(
            f"front-facing view of the {gender_en} model, facing the camera directly, "
            "clear and unobstructed view of the garment, symmetrical presentation, "
            "ideal for e-commerce product display, neutral and natural posture"
        )

    elif side_view == "Sol çapraz":
        parts.append(
            f"three-quarter angle view from the left side, {gender_en} model slightly turned, "
            "showing both front and side of the garment, natural relaxed posture, "
            "enhances depth and fabric drape, suitable for lingerie and sleepwear catalog"
        )

    elif side_view == "Arka":
        parts.append(
            f"back view of the {gender_en} model, facing away from the camera, "
            "clear visibility of the back design of the garment, straps, seams, and fit, "
            "neutral posture, professional catalog presentation"
        )

    # Ortam
    if scene_style == "E-commerce studio":
        parts.append(
            "in a professional e-commerce studio, clean white seamless background, "
            "even softbox lighting, no props"
        )
        
    elif scene_style == "Lifestyle (plaj)":
        parts.append(
            "on a sunny sandy beach with turquoise sea in background, soft golden hour light, "
            "relaxed vacation atmosphere"
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
        f"WRITTEN PRODUCT INSTRUCTIONS: {product_text}. "
        "These written instructions must be followed strictly. "
        "If the written instructions include a Pantone code, HEX code, exact color name, fabric type, button count, pocket detail, collar type, pattern description or correction, those details override unclear or conflicting details in the image. "
        "The garment must be clearly visible, accurate to the written description and realistically fitted to the body."
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


def history_entry(product_text, shot_type, side_view, scene_style, extra_notes, gender_tr):
    return (
        f"[SHOT={shot_type}, SCENE={scene_style}, CINSIYET={gender_tr}] "
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
            "gemini-3-pro-image",  # hesabında bu model yoksa flash kullan
            "gemini-3.1-flash-image",
        ],
    )

    # CİNSİYET SEÇİMİ EKLENDİ
    gender_tr = st.selectbox(
        "Cinsiyet",
        ["Bayan Değil Kadın", "Erkek"],
        index=0  # Varsayılan olarak Kadın seçili
    )
    
    # İngilizce karşılığını belirle
    gender_en = "male" if gender_tr == "Erkek" else "female"

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
            "Lifestyle (plaj)",
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
        ["1K", "2K","4k"],
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
    placeholder="Örn: Erkek pijama takımı. Renk: Pantone 19-4024 Navy / HEX #1F2A44. Kumaş: pamuk modal. Yaka: gömlek yaka. Düğme: 5 adet. Cep: sol göğüste tek cep. Desen: ince dikey çizgili. Fotoğraftaki kesim ve ürün detayları korunmalı.",
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
            entry = history_entry(product_text, shot_type, side_view, scene_style, extra_notes, gender_tr)
            st.session_state["history"].append(entry)

            # 2) Prompt'u hazırla - gender_en parametresini ekledik
            base_prompt = build_prompt(product_text, shot_type, side_view, scene_style, extra_notes, gender_en)
            base_prompt += f", aspect ratio {aspect_ratio}, target resolution {resolution}."

            # --- Görselleri oku (PIL) ---
            pil_product_images = [Image.open(f) for f in (product_files or [])[:3]]
            pil_model_images   = [Image.open(f) for f in (model_files or [])[:5]]
            
            # 3) contents dizisini hazırlayalım
            contents = []
            
            # System prompt'u dinamik olarak oluştur
            SYSTEM_PROMPT = get_system_prompt(gender_en)
            
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text="SYSTEM INSTRUCTIONS (follow strictly):\n" + SYSTEM_PROMPT)]
                )
            )
            
            # 4) Geçmiş bağlam (opsiyonel)
            if use_context:
                for h in st.session_state["history"][:-1]:
                    contents.append(
                        types.Content(
                            role="user",
                            parts=[types.Part(text=f"Previous request preferences (for consistency, do not repeat): {h}")]
                        )
                    )
            
            # 5) Ürün görselleri (sadece ürün detayları için)
            if pil_product_images:
                # Önce açıklama metni
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text="PRODUCT REFERENCE IMAGES (use ONLY garment details; ignore any human model in these images):")]
                    )
                )
                # Sonra her görsel için ayrı content
                for img in pil_product_images:
                    contents.append(types.Content(role="user", parts=[pil_to_part(img)]))
            
            # 6) Manken görselleri (sadece manken referansı için)
            if pil_model_images:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text="MODEL REFERENCE IMAGES (use ONLY as body/pose/angle reference; do not copy identity):")]
                    )
                )
                for img in pil_model_images:
                    contents.append(types.Content(role="user", parts=[pil_to_part(img)]))
            
            # 7) Asıl kullanıcı promptu - EN SONA EKLENMELİ
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text=base_prompt)]
                )
            )
"""
            # 8) Gemini'yi çağır
            with st.spinner("Gemini ile görsel üretiliyor..."):
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                )
            
            # 9) Görselleri çek (yeni SDK: candidates[*].content.parts)
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
"""
            # 8) Gemini'yi çağır
# Minimum 3 görsel üret, fazlası gelirse hepsini göster

MIN_IMAGES = 3
MAX_ATTEMPTS = 5

image_parts = []
attempt = 0

with st.spinner("Gemini ile görseller üretiliyor..."):

    while len(image_parts) < MIN_IMAGES and attempt < MAX_ATTEMPTS:
        attempt += 1

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
        )

        candidates = getattr(response, "candidates", None)

        if candidates:
            for cand in candidates:
                content = getattr(cand, "content", None)
                parts = getattr(content, "parts", None)

                if parts:
                    for part in parts:
                        if (
                            getattr(part, "inline_data", None) is not None
                            and getattr(
                                part.inline_data,
                                "mime_type",
                                ""
                            ).startswith("image/")
                        ):
                            image_parts.append(part)
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
