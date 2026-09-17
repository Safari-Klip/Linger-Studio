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
- If separate model reference images are provided, use them ONLY as a general reference for body proportions.
- NEVER use the pose direction, camera angle or viewing angle from model reference images.
- The camera/view direction selected in the CURRENT USER REQUEST is the absolute source of truth.
- The selected camera/view direction overrides the angle shown in all product and model reference images.
- Use natural and realistic body language appropriate to the selected scene.
- For e-commerce studio scenes, use a neutral catalog pose with relaxed arms and realistic posture.
- For lifestyle scenes, use relaxed candid fashion-editorial body language, natural weight distribution and subtle realistic movement.
- Lifestyle poses must never become exaggerated, theatrical or overly fashion-forward.
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
- For e-commerce studio scenes, the model should stand vertically and clearly present the garment.
- For lifestyle scenes, allow natural relaxed posture and subtle body movement while keeping the garment clearly visible.
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
            "entire outfit visible from head to toe, full head, hair and feet completely visible, "
            "leave a small comfortable margin above the head and a minimal margin below the feet, "
            "do not crop the top of the head, hair, chin, toes or heels, "
            "balanced proportions, centered subject, tight but comfortable framing, "
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
            "in a professional high-key e-commerce photography studio, "
            "clean bright white seamless studio background, "
            "bright and evenly illuminated backdrop, "
            "professional softbox studio lighting on the model, "
            "soft natural studio shadows only, "
            "no gray background, no dark gray background, no beige background, "
            "no colored background, no gradient backdrop, no moody lighting, "
            "no dark corners, no props"
        )
    
    elif scene_style == "Lifestyle (yatak odası)":
        parts.append(
            "in a realistic premium bedroom environment appropriate for sleepwear photography, "
            "the exact bedroom design and layout should vary naturally between generations, "
            "and must follow any environment styling described in the user's extra notes, "
            "it may feel like a modern home bedroom, refined contemporary bedroom, "
            "minimal Scandinavian bedroom, warm cozy bedroom or softly styled feminine bedroom, "
            "natural daylight, realistic textile and furniture textures, believable depth, "
            "subtle lived-in details and slight natural imperfections, "
            "the model should feel naturally present in the room rather than artificially posed, "
            "the garment must remain clearly visible and be the visual focus, "
            "do not repeat the exact same room layout, furniture arrangement or bed styling every time, "
            "no CGI-like interior, no artificial showroom appearance, "
            "no excessive decoration, no overly perfect symmetry"
        )
    
    elif scene_style == "Lifestyle (salon / ev içi)":
        parts.append(
            "in a realistic stylish contemporary home living space appropriate for premium sleepwear, "
            "with believable furniture, soft textiles and natural architectural depth, "
            "the exact decor, furniture arrangement and styling should vary between generations "
            "and follow the user's extra notes, "
            "soft natural daylight, warm neutral interior atmosphere, "
            "relaxed candid body language, as if captured during a genuine moment at home, "
            "garment remains clearly visible and is the main focus, "
            "no staged furniture showroom look, no CGI-like interior, "
            "no excessive luxury styling or unnatural symmetry"
        )
    
    elif scene_style == "Lifestyle (otel odası)":
        parts.append(
            "in a realistic premium hotel room or boutique hotel suite, "
            "refined but believable interior design, high-quality bedding and subtle architectural details, "
            "the exact room design, materials, lighting and furniture should vary naturally "
            "and follow the user's extra notes, "
            "soft window daylight or elegant diffused hotel lighting, "
            "relaxed candid fashion photography, natural body language, "
            "garment remains clearly visible and is the visual focus, "
            "no exaggerated five-star fantasy interior, no CGI look, "
            "no overly staged or perfectly symmetrical composition"
        )
    
    elif scene_style == "Lifestyle (pencere önü / sabah ışığı)":
        parts.append(
            "near a large window in a realistic home or hotel interior, "
            "soft natural morning daylight entering from the side, "
            "subtle realistic highlights and shadows, "
            "the surrounding interior should vary naturally and follow the user's extra notes, "
            "quiet morning-routine feeling, relaxed candid posture, "
            "natural weight distribution and believable facial expression, "
            "garment remains clearly visible and is the main focus, "
            "no artificial glow, no overexposed window, no dramatic fashion pose"
        )
    
    elif scene_style == "Lifestyle (balkon / teras)":
        parts.append(
            "on a realistic private balcony or terrace connected to a stylish home or hotel, "
            "soft natural daylight, believable outdoor depth and subtle environmental details, "
            "the architecture, furniture and surrounding atmosphere should vary naturally "
            "and follow the user's extra notes, "
            "relaxed morning or evening-at-home feeling, candid natural body language, "
            "garment remains clearly visible and is the main focus, "
            "no fantasy resort look, no exaggerated sunset, no artificial CGI scenery"
        )
    
    elif scene_style == "Lifestyle (okuma köşesi)":
        parts.append(
            "in a realistic comfortable reading corner inside a contemporary home or hotel, "
            "with a chair, sofa or subtle soft furnishing elements where appropriate, "
            "the exact setting and decor should vary and follow the user's extra notes, "
            "soft natural daylight, intimate but non-sexual everyday atmosphere, "
            "relaxed candid posture and realistic body language, "
            "garment remains clearly visible and is the main focus, "
            "no theatrical posing, no artificial staged showroom look"
        )
    
    elif scene_style == "Lifestyle (mutfak / kahvaltı)":
        parts.append(
            "in a realistic contemporary kitchen or breakfast area during a relaxed morning routine, "
            "soft natural daylight, believable everyday home details, "
            "the interior style, counter materials and background elements should vary naturally "
            "and follow the user's extra notes, "
            "candid relaxed body language as if captured during a real morning at home, "
            "garment remains clearly visible and is the main focus, "
            "no cluttered commercial kitchen, no advertising-set appearance, no CGI interior"
        )
    
    elif scene_style == "Lifestyle (tatil evi / cozy cabin)":
        parts.append(
            "inside a realistic stylish holiday home, countryside house or cozy cabin environment, "
            "natural materials, soft textiles and believable architectural details, "
            "the exact location and styling should vary naturally and follow the user's extra notes, "
            "soft natural daylight and relaxed lived-in atmosphere, "
            "candid premium lifestyle photography, natural body posture, "
            "garment remains clearly visible and is the visual focus, "
            "no fantasy cabin, no excessive rustic decoration, no CGI-like environment"
        )
    
    elif scene_style == "Lifestyle (plaj)":
        parts.append(
            "on a real natural beach with believable sand and sea tones, "
            "natural daylight with realistic highlights and shadows, "
            "subtle wind movement in hair and fabric, "
            "the beach environment and composition should vary naturally "
            "and follow the user's extra notes, "
            "relaxed candid body language as if captured during a genuine vacation moment, "
            "garment remains clearly visible and is the main focus, "
            "no artificial tropical postcard look, no oversaturated turquoise water, "
            "no exaggerated golden glow, no CGI scenery, no dramatic fashion pose"
        )
    
    elif scene_style == "Lifestyle (spor salonu)":
        parts.append(
            "in a realistic premium contemporary fitness or wellness studio, "
            "natural architectural depth, authentic materials and believable equipment placement, "
            "the exact studio environment should vary naturally and follow the user's extra notes, "
            "soft diffused daylight combined with subtle professional interior lighting, "
            "relaxed natural body language as if captured between movements, "
            "garment remains clearly visible and is the main focus, "
            "no excessive neon lighting, no glossy CGI environment, "
            "no exaggerated athletic pose"
        )
    
    else:
        parts.append(
            "in a minimal softly lit neutral environment, "
            "clean understated styling, realistic depth and natural soft lighting, "
            "with no distracting props or artificial CGI appearance"
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


def part_to_streamlit_image(part, force_size=None):
    img = decode_gemini_image(part).convert("RGB")

    if force_size:
        target_w, target_h = force_size

        # Görselin en-boy oranını koruyarak hedef alana sığdır.
        # Crop veya stretch yapılmaz.
        scale = min(
            target_w / img.width,
            target_h / img.height
        )

        new_w = round(img.width * scale)
        new_h = round(img.height * scale)

        img = img.resize(
            (new_w, new_h),
            Image.Resampling.LANCZOS
        )

        # Kesmeden tam hedef ölçüde beyaz canvas oluştur.
        canvas = Image.new(
            "RGB",
            (target_w, target_h),
            "white"
        )

        # Görseli canvas'ın ortasına yerleştir.
        x = (target_w - new_w) // 2
        y = (target_h - new_h) // 2

        canvas.paste(img, (x, y))
        img = canvas

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
            "Lifestyle (yatak odası)",
            "Lifestyle (salon / ev içi)",
            "Lifestyle (otel odası)",
            "Lifestyle (pencere önü / sabah ışığı)",
            "Lifestyle (balkon / teras)",
            "Lifestyle (okuma köşesi)",
            "Lifestyle (mutfak / kahvaltı)",
            "Lifestyle (tatil evi / cozy cabin)",
            "Lifestyle (plaj)",
            "Lifestyle (spor salonu)",
            "Minimal (nötr arka plan)",
        ],
    )

    aspect_ratio = st.selectbox(
        "Görsel oranı",
        ["1:1", "4:5", "3:4", "9:16", "16:9", "5:6", "1200x1560 px"],
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
            prompt_aspect_ratio = "10:13" if aspect_ratio == "1200x1560 px" else aspect_ratio
            base_prompt += f", aspect ratio {prompt_aspect_ratio}, target resolution {resolution}."
            if side_view == "Ön":
                base_prompt += """
            ABSOLUTE CAMERA VIEW REQUIREMENT:
            FRONT VIEW ONLY.
            The model must face directly toward the camera.
            Both shoulders and both hips must face forward symmetrically.
            Do not use a three-quarter view, side view or rotated body pose.
            Ignore the camera angle and pose shown in ALL reference images.
            """
            
            elif side_view == "Sol çapraz":
                base_prompt += """
            ABSOLUTE CAMERA VIEW REQUIREMENT:
            LEFT THREE-QUARTER VIEW ONLY.
            The model must be turned approximately 30-45 degrees to show the front and left side.
            Do not use a straight front, right three-quarter, profile or back view.
            Ignore the camera angle and pose shown in ALL reference images.
            """
            
            elif side_view == "Arka":
                base_prompt += """
            ABSOLUTE CAMERA VIEW REQUIREMENT:
            BACK VIEW ONLY.
            The model must face directly away from the camera.
            The back of the garment must be clearly visible.
            Do not use a front, three-quarter front or side view.
            Ignore the camera angle and pose shown in ALL reference images.
            """
                
            # --- Görselleri oku (PIL) ---
            pil_product_images = [Image.open(f) for f in (product_files or [])[:3]]
            pil_model_images   = [Image.open(f) for f in (model_files or [])[:5]]
            
            # 3) contents dizisini hazırlayalım
            contents = []
            
            # System prompt'u dinamik olarak oluştur
            SYSTEM_PROMPT = get_system_prompt(gender_en)
            
            contents.append(types.Part(text="SYSTEM INSTRUCTIONS (follow strictly):\n" + SYSTEM_PROMPT))
            
            # 4) Geçmiş bağlam (opsiyonel)
            if use_context:
                for h in st.session_state["history"][:-1]:
                    contents.append(types.Part(text=f"Previous request preferences (for consistency, do not repeat): {h}"))
            
            # 5) Ürün görselleri (sadece ürün detayları için)
            if pil_product_images:
                # Önce açıklama metni
                contents.append(types.Part(text="PRODUCT REFERENCE IMAGES (use ONLY garment details; ignore any human model in these images):"))
                # Sonra her görsel için ayrı content
                for img in pil_product_images:
                    contents.append(pil_to_part(img))
            
            # 6) Manken görselleri (sadece manken referansı için)
            if pil_model_images:
                contents.append(types.Part(text="MODEL REFERENCE IMAGES (use ONLY as general body proportion reference; NEVER copy pose, camera angle or viewing direction; do not copy identity):"))
                for img in pil_model_images:
                    contents.append(pil_to_part(img))
            
            # 7) Asıl kullanıcı promptu - EN SONA EKLENMELİ
            contents.append(types.Part(text=base_prompt))
            
            # 8) Gemini'yi çağır
            # Minimum 3 görsel üret, fazlası gelirse hepsini göster

            MIN_IMAGES = 3
            MAX_ATTEMPTS = 5

            image_parts = []
            attempt = 0

            with st.spinner("Gemini ile görseller üretiliyor..."):
            
                while len(image_parts) < MIN_IMAGES and attempt < MAX_ATTEMPTS:
                    attempt += 1
            
                    chat = client.chats.create(
                        model=model_name,
                    )
            
                    response = chat.send_message(contents)
                    

                    # Bu çağrıdaki tüm görselleri al
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
                        force_size = (1200, 1560) if aspect_ratio == "1200x1560 px" else None
                        buf = part_to_streamlit_image(part, force_size=force_size)
                        st.image(buf, caption=f"Sonuç #{idx+1}")
                        st.download_button(
                            label="🔽 İndir",
                            data=buf,
                            file_name=f"gemini_output_{idx+1}.png",
                            mime="image/png",
                        )

        except Exception as e:
            st.error(f"Hata oluştu: {e}")
