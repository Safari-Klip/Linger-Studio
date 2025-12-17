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
#     GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

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

# Session state'te login durumu saklanır
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
def build_prompt(product_text, shot_type, scene_style, extra_notes):
    parts = []

    # Kadraj
    if shot_type == "Full body":
        parts.append(
            "full body fashion shot of a female model, standing naturally, "
            "entire outfit visible from head to toe, balanced proportions, "
            "catalog-style composition"
        )

    elif shot_type == "Upper body":
        parts.append(
            "upper body fashion shot of a female model, framed from shoulders to waist, "
            "clear focus on the top garment, natural posture, clean and professional "
            "e-commerce composition"
        )

    elif shot_type == "Lower body":
        parts.append(
            "lower body fashion shot of a female model, framed from waist to mid-thigh or knees, "
            "clear focus on the bottom garment, accurate fit and fabric details, "
            "clean catalog-style composition"
        )

    #Side/Yön
    if side_view == "Ön":
        parts.append(
            "front-facing view of the female model, facing the camera directly, "
            "clear and unobstructed view of the garment, symmetrical presentation, "
            "ideal for e-commerce product display, neutral and natural posture"
    )

    elif side_view == "Sol çapraz":
        parts.append(
            "three-quarter angle view from the left side, female model slightly turned, "
            "showing both front and side of the garment, natural relaxed posture, "
            "enhances depth and fabric drape, suitable for lingerie and sleepwear catalog"
    )


    elif side_view == "Arka":
        parts.append(
            "back view of the female model, facing away from the camera, "
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


def history_entry(product_text, shot_type, scene_style, extra_notes):
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
        ["1:1", "4:5", "3:4", "9:16", "16:9","5:6"],
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
            entry = history_entry(product_text, shot_type, scene_style, extra_notes)
            st.session_state["history"].append(entry)

            # 2) Prompt'u hazırla
            base_prompt = build_prompt(product_text, shot_type, scene_style, extra_notes)
            base_prompt += f", aspect ratio {aspect_ratio}, target resolution {resolution}."

            # 3) contents dizisini hazırlayalım
            contents = []

            if use_context:
                for h in st.session_state["history"][:-1]:  # son entry şu anki istek
                    contents.append(
                        f"Previous request style and preferences "
                        f"(use for consistency, do not repeat): {h}"
                    )

            # Şu anki asıl prompt
            contents.append(base_prompt)

            # Referans görselleri ekle
            pil_images = []

            if product_files:
                for f in product_files[:3]:
                    pil_images.append(Image.open(f))

            if model_files:
                for f in model_files[:5]:
                    pil_images.append(Image.open(f))

            contents.extend(pil_images)

            # 4) Gemini'yi çağır
            with st.spinner("Gemini ile görsel üretiliyor..."):
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
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
