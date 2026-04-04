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

# ================= CONFIG =================
st.set_page_config(
    page_title="Input Flow Meter MBI",
    layout="wide",
    initial_sidebar_state="collapsed"
)

EXCEL_FILE = "database_meteran.xlsx"
UPLOAD_FOLDER = "uploads"
tz_jkt = pytz.timezone('Asia/Jakarta')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= OCR =================
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False, verbose=False)

reader = load_reader()

# 🔥 CROP STABIL (khusus meter kamu)
def crop_meter_area(img):
    h, w = img.shape[:2]
    return img[int(h*0.35):int(h*0.65), int(w*0.15):int(w*0.85)]

# 🔥 PREPROCESS PALING AKURAT
def preprocess_meter(img):
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    # Kontras tinggi
    clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)

    # Blur ringan
    blur = cv2.GaussianBlur(enhanced, (3,3), 0)

    # Threshold fix (lebih stabil untuk display digital)
    _, thresh = cv2.threshold(blur, 120, 255, cv2.THRESH_BINARY)

    return thresh

# 🔥 OCR KHUSUS ANGKA
def read_meter(img):
    return reader.readtext(
        img,
        detail=0,
        allowlist='0123456789.',
        paragraph=False
    )

# 🔥 FILTER HASIL OCR
def extract_meter_value(texts):
    text = " ".join(texts)

    mapping = {
        'O':'0','D':'0','Q':'0',
        'B':'8','S':'5','I':'1','L':'1'
    }

    for k,v in mapping.items():
        text = text.replace(k,v)

    text = re.sub(r'[^0-9.]', '', text)

    matches = re.findall(r'\d{5,8}(?:\.\d{1,3})?', text)

    return max(matches, key=len) if matches else "Cek Foto"

# ================= SAVE =================
def save_data(df):
    for _ in range(3):
        try:
            df.to_excel(EXCEL_FILE, index=False)
            return True
        except:
            time.sleep(1)
    return False

# ================= UI =================
st.title("📟 Flow Meter Recording")
st.write(f"🕒 {datetime.now(tz_jkt).strftime('%d-%m-%Y %H:%M:%S')} WIB")

tab1, tab2 = st.tabs(["📸 Kamera", "📁 Upload"])

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
    if 'history' not in st.session_state:
        st.session_state.history = []

    new_data = []
    now = datetime.now(tz_jkt)

    for f in files:
        fname = f.name if hasattr(f,'name') else f"{now.timestamp()}.jpg"

        if fname not in st.session_state.history:
            try:
                img = Image.open(f)
                img = img.resize((800,800))

                path = os.path.join(UPLOAD_FOLDER, fname)
                img.save(path)

                img_np = np.array(img)

                # 🔥 CROP STABIL
                crop = crop_meter_area(img_np)

                # 🔥 PREPROCESS
                processed = preprocess_meter(crop)

                # 🔥 OCR
                texts = read_meter(processed)
                angka = extract_meter_value(texts)

            except Exception as e:
                angka = "Error OCR"

            new_data.append({
                "Tanggal": now.strftime("%d-%m-%Y"),
                "Jam": now.strftime("%H:%M"),
                "Nama Meteran": "",
                "Angka Meteran": str(angka),
                "Foto": fname
            })

            st.session_state.history.append(fname)

    if new_data:
        df_new = pd.DataFrame(new_data)

        if os.path.exists(EXCEL_FILE):
            df_old = pd.read_excel(EXCEL_FILE, dtype=str)
            df = pd.concat([df_old, df_new], ignore_index=True)
        else:
            df = df_new

        if save_data(df):
            st.success("Data tersimpan!")
            st.rerun()
        else:
            st.error("Gagal simpan")

# ================= VERIFIKASI =================
if os.path.exists(EXCEL_FILE):
    df = pd.read_excel(EXCEL_FILE, dtype=str)

    if not df.empty:
        st.divider()
        st.header("🔍 Verifikasi Data Terakhir")

        last = df.iloc[-1]
        idx = df.index[-1]

        col1, col2 = st.columns([1.2,1])

        with col1:
            img_path = os.path.join(UPLOAD_FOLDER, last['Foto'])
            if os.path.exists(img_path):
                st.image(img_path, width=400)

        with col2:
            tgl = st.date_input("Tanggal", datetime.now(tz_jkt))
            jam = st.text_input("Jam", value=last['Jam'])
            nama = st.text_input("Nama Meteran", value=last['Nama Meteran'])
            angka = st.text_input("Angka Meteran (Edit jika salah)", value=last['Angka Meteran'])

            if st.button("✅ KONFIRMASI & SIMPAN"):
                df.at[idx,'Tanggal'] = tgl.strftime("%d-%m-%Y")
                df.at[idx,'Jam'] = jam
                df.at[idx,'Nama Meteran'] = nama
                df.at[idx,'Angka Meteran'] = angka

                save_data(df)
                st.success("Data berhasil diverifikasi!")
                st.rerun()

        st.subheader("📊 Histori Pencatatan (Terbaru di Atas)")

        df_show = df.copy()
        df_show.insert(0,"Pilih",False)

        edited = st.data_editor(
            df_show.iloc[::-1],
            column_config={"Pilih": st.column_config.CheckboxColumn()},
            disabled=["Tanggal","Jam","Nama Meteran","Angka Meteran","Foto"],
            use_container_width=True
        )

        pilih = edited[edited["Pilih"]==True]

        if not pilih.empty:
            if st.button(f"🗑️ Hapus {len(pilih)} Data"):
                df = df.drop(pilih.index)
                save_data(df)
                st.warning("Data berhasil dihapus!")
                st.rerun()
