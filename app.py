import streamlit as st
import pandas as pd
import easyocr
import cv2
import os
import re
import numpy as np
from datetime import datetime
from PIL import Image
import pytz
import time
import io
import ssl

# ================= ANTI SSL =================
ssl._create_default_https_context = ssl._create_unverified_context

# ================= CONFIG =================
st.set_page_config(page_title="Input Flow Meter MBI", layout="wide")

EXCEL_FILE = "database_meteran.xlsx"
UPLOAD_FOLDER = "uploads"
tz_jkt = pytz.timezone('Asia/Jakarta')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= SESSION =================
if "saved" not in st.session_state:
    st.session_state.saved = False

# ================= OCR =================
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

try:
    reader = load_reader()
except:
    st.error("❌ OCR gagal load")
    st.stop()

# ================= OCR LOGIC (TIDAK DIUBAH) =================
def advanced_pre_process(img_np):
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    return cv2.GaussianBlur(enhanced, (3, 3), 0)

def robust_extract_logic(text_list):
    full_text = " ".join(text_list).upper()
    for unit in ["KWH","KVARH","M3/H","M3","KVAR"]:
        full_text = full_text.replace(unit,"")

    mapping = {'O':'0','D':'0','Q':'0','B':'8','S':'5','I':'1','L':'1','T':'7','Z':'2','G':'6','A':'4'}
    for k,v in mapping.items():
        full_text = full_text.replace(k,v)

    full_text = full_text.replace(",",".")
    pattern = re.findall(r'\d{5,8}(?:\.\d{1,3})?', full_text)

    return max(pattern, key=len) if pattern else "Cek Foto"

# ================= SAVE (ANTI GAGAL) =================
def save_data(df):
    for _ in range(5):
        try:
            df.to_excel(EXCEL_FILE, index=False)
            return True
        except:
            time.sleep(1)
    return False

# ================= UI =================
st.title("📟 Flow Meter Recording")

tab1, tab2 = st.tabs(["📸 Kamera","📁 Upload"])

files = []

with tab1:
    cam = st.camera_input("Ambil foto meteran")
    if cam:
        files.append(cam)

with tab2:
    upload = st.file_uploader("Upload gambar", type=['jpg','jpeg','png'], accept_multiple_files=True)
    if upload:
        files.extend(upload)

# ================= PROCESS =================
if files:
    now = datetime.now(tz_jkt)

    for f in files:
        try:
            fname = f.name if hasattr(f,'name') else f"{int(time.time())}.jpg"

            img = Image.open(f)
            img = img.resize((400,400))  # ⚡ lebih cepat
            path = os.path.join(UPLOAD_FOLDER, fname)
            img.save(path)

            # ⚡ OCR langsung (lebih cepat)
            result = reader.readtext(np.array(img), detail=0)
            angka = robust_extract_logic(result)

        except:
            angka = "Error OCR"

        st.divider()

        col1, col2 = st.columns([1,1])

        with col1:
            st.image(img, caption="Foto Meteran")

        with col2:
            tanggal = st.text_input("Tanggal", value=now.strftime("%d-%m-%Y"), key=f"tgl_{fname}")
            jam = st.text_input("Jam", value=now.strftime("%H:%M"), key=f"jam_{fname}")
            nama = st.text_input("Nama Meteran", key=f"nama_{fname}")

            angka_final = st.text_input(
                "Angka Meteran",
                value=str(angka),
                key=f"angka_{fname}"
            )

            save_clicked = st.button("✅ SIMPAN", key=f"save_{fname}")

            if save_clicked and not st.session_state.saved:

                # ================= VALIDASI =================
               
