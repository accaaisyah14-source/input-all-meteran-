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
st.set_page_config(
    page_title="Input Flow Meter MBI",
    layout="wide",
    initial_sidebar_state="collapsed"
)

EXCEL_FILE = "database_meteran.xlsx"
UPLOAD_FOLDER = "uploads"
tz_jkt = pytz.timezone('Asia/Jakarta')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= SESSION =================
if "last_saved" not in st.session_state:
    st.session_state.last_saved = None

# ================= OCR =================
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

reader = load_reader()

def advanced_pre_process(img_np):
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    return cv2.GaussianBlur(enhanced, (3, 3), 0)

def robust_extract_logic(text_list):
    full_text = " ".join(text_list).upper()

    for unit in ["KWH","KVARH","M3/H","M3","KVAR"]:
        full_text = full_text.replace(unit,"")

    mapping = {
        'O':'0','D':'0','Q':'0',
        'B':'8','S':'5',
        'I':'1','L':'1',
        'T':'7','Z':'2',
        'G':'6','A':'4'
    }

    for k,v in mapping.items():
        full_text = full_text.replace(k,v)

    full_text = full_text.replace(",",".")
    pattern = re.findall(r'\d{5,8}(?:\.\d{1,3})?', full_text)

    return max(pattern, key=len) if pattern else "Cek Foto"

# ================= SAVE (MULTI USER SAFE) =================
def save_with_lock(df):
    lock_file = EXCEL_FILE + ".lock"

    while os.path.exists(lock_file):
        time.sleep(0.3)

    try:
        open(lock_file, "w").close()

        with pd.ExcelWriter(EXCEL_FILE, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)

    finally:
        if os.path.exists(lock_file):
            os.remove(lock_file)

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
                "Angka Meteran (Edit jika salah)",
                value=str(angka),
                key=f"angka_{fname}"
            )

            if st.button("✅ KONFIRMASI & SIMPAN", key=f"save_{fname}"):

                # VALIDASI
                if nama.strip() == "":
                    st.warning("Nama meteran wajib diisi!")
                    st.stop()

                if angka_final.strip() == "":
                    st.warning("Angka kosong!")
                    st.stop()

                if not angka_final.replace('.', '').isdigit():
                    st.warning("Format angka salah!")
                    st.stop()

                unique_key = f"{tanggal}_{jam}_{nama}_{angka_final}"

                if st.session_state.last_saved == unique_key:
                    st.warning("Data sudah tersimpan!")
                    st.stop()

                try:
                    data_baru = pd.DataFrame([{
                        "Tanggal": tanggal,
                        "Jam": jam,
                        "Nama Meteran": nama,
                        "Angka Meteran": float(angka_final),
                        "Foto": fname
                    }])

                    if os.path.exists(EXCEL_FILE):
                        df_old = pd.read_excel(EXCEL_FILE)
                    else:
                        df_old = pd.DataFrame()

                    df = pd.concat([df_old, data_baru], ignore_index=True)

                    save_with_lock(df)

                    st.session_state.last_saved = unique_key

                    st.success("Data tersimpan!")
                    st.rerun()

                except Exception as e:
                    st.error(f"Gagal simpan: {e}")

# ================= HISTORI =================
if os.path.exists(EXCEL_FILE):
    df = pd.read_excel(EXCEL_FILE)

    if not df.empty:
        st.divider()
        st.subheader("📊 Histori Pencatatan")

        st.dataframe(df.iloc[::-1], use_container_width=True)

        # preview foto
        #for i, row in df.iloc[::-1].iterrows():
            #with st.expander(f"{row['Tanggal']} | {row['Nama Meteran']}"):
                #path = os.path.join(UPLOAD_FOLDER, row["Foto"])
                #if os.path.exists(path):
                    #st.image(path, width=300)

        # ================= HAPUS MULTI =================
        st.divider()
        st.subheader("🗑️ Hapus Banyak Data")

        df_reset = df.reset_index()

        pilih = st.multiselect(
            "Pilih data yang ingin dihapus",
            df_reset.index,
            format_func=lambda x: f"{df_reset.loc[x,'Tanggal']} | {df_reset.loc[x,'Nama Meteran']} | {df_reset.loc[x,'Angka Meteran']}"
        )

        if st.button("❌ Hapus Data Terpilih"):
            if len(pilih) == 0:
                st.warning("Pilih data dulu!")
            else:
                try:
                    df = df.drop(pilih)
                    save_with_lock(df)
                    st.success(f"{len(pilih)} data berhasil dihapus!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal hapus: {e}")

        # ================= DOWNLOAD =================
        st.divider()

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)

        st.download_button(
            label="📥 Download Excel",
            data=output.getvalue(),
            file_name="data_meteran.xlsx"
        )
