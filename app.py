import streamlit as st
import pandas as pd
import easyocr
import cv2
import os
import re
from datetime import datetime
from PIL import Image
import numpy as np

# Konfigurasi
EXCEL_FILE = "database_meteran.xlsx"
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr()

def pre_process_vision(img_np):
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    max_dim = 1600
    h, w = gray.shape[:2]
    if w > max_dim or h > max_dim:
        scale = max_dim / max(w, h)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8)).apply(gray)

def extract_logic(text_list):
    """Logika pembersihan ekstra untuk mencegah angka tertukar (0/8, 1/7, 2/5)"""
    full_text = " ".join(text_list).upper().replace(',', '.')
    
    # 1. Mapping karakter yang sering salah baca oleh AI
    mapping = {
        'O': '0', 'D': '0', 'Q': '0', # Koreksi untuk angka 0
        'B': '8', 'S': '5', 'G': '6', # Koreksi untuk angka 8, 5, 6
        'I': '1', 'L': '1', 'T': '7', # Koreksi untuk angka 1 dan 7
        'Z': '2', 'A': '4'
    }
    for k, v in mapping.items():
        full_text = full_text.replace(k, v)
    
    # 2. Gunakan Regex untuk mencari angka yang masuk akal (5-8 digit)
    # Menghindari pembacaan simbol kecil di background sebagai angka
    pattern = re.findall(r'\d{5,8}(?:\.\d{1,3})?', full_text)
    
    # 3. Filter Validasi: Abaikan angka yang hanya terdiri dari 1 jenis karakter (misal: 0000)
    valid = [p for p in pattern if len(set(p.replace('.',''))) > 1]
    valid.sort(key=len, reverse=True)
    
    return valid[0] if valid else "Cek Foto"

# --- UI ---
st.set_page_config(page_title="Input Meteran PT. Multi Bintang Indonesia", layout="wide")
st.title("Input Meteran PT. Multi Bintang Indonesia")

metode = st.radio("Pilih Metode Input:", ("📷 Kamera Langsung", "📁 Upload Galeri"), horizontal=True)

source_files = []
if metode == "📷 Kamera Langsung":
    cam_file = st.camera_input("Jepret Meteran")
    if cam_file: source_files = [cam_file]
else:
    up_files = st.file_uploader("Upload Foto", type=['jpg','jpeg','png'], accept_multiple_files=True)
    if up_files: source_files = up_files

if source_files:
    if 'history' not in st.session_state: st.session_state.history = []
    new_entries = []
    for f in source_files:
        file_id = f.name if hasattr(f, 'name') else f"camera_{datetime.now().strftime('%H%M%S')}.jpg"
        if file_id not in st.session_state.history:
            with st.spinner('Menganalisis...'):
                img_path = os.path.join(UPLOAD_FOLDER, file_id)
                with open(img_path, "wb") as sf: sf.write(f.getbuffer())
                img_pil = Image.open(f)
                processed = pre_process_vision(np.array(img_pil))
                res = reader.readtext(processed, detail=0)
                angka = extract_logic(res)
                new_entries.append({
                    "Tanggal": datetime.now().strftime("%d-%m-%Y"),
                    "Jam": datetime.now().strftime("%H:%M:%S"),
                    "Nama Meteran": "Meteran",
                    "Angka Meteran": angka,
                    "File_Path": file_id
                })
                st.session_state.history.append(file_id)
    if new_entries:
        df_new = pd.DataFrame(new_entries)
        if os.path.exists(EXCEL_FILE):
            pd.concat([pd.read_excel(EXCEL_FILE), df_new], ignore_index=True).to_excel(EXCEL_FILE, index=False)
        else:
            df_new.to_excel(EXCEL_FILE, index=False)
        st.rerun()

if os.path.exists(EXCEL_FILE):
    df_db = pd.read_excel(EXCEL_FILE)
    if not df_db.empty:
        st.divider()
        st.header("🔍 Verifikasi & Penamaan")
        last_idx, last_row = df_db.index[-1], df_db.iloc[-1]
        c1, c2 = st.columns([1, 1])
        with c1:
            if 'File_Path' in last_row:
                foto_path = os.path.join(UPLOAD_FOLDER, str(last_row['File_Path']))
                if os.path.exists(foto_path):
                    st.image(foto_path, caption="Foto Terakhir", width=450)
        with c2:
            st.subheader("📝 Koreksi")
            e_nama = st.text_input("Nama Meteran", value=str(last_row.get('Nama Meteran', '')))
            e_angka = st.text_input("Angka Meteran", value=str(last_row.get('Angka Meteran', '')))
            if st.button("✅ Simpan Data", use_container_width=True):
                df_db.at[last_idx, 'Nama Meteran'], df_db.at[last_idx, 'Angka Meteran'] = e_nama, e_angka
                df_db.to_excel(EXCEL_FILE, index=False); st.rerun()
            df_db['LBL'] = df_db['Nama Meteran'] + " (" + df_db['Jam'] + ")"
            list_hapus = st.multiselect("Pilih data untuk dihapus:", df_db['LBL'].tolist())
            if st.button("🗑️ Hapus Terpilih", type="primary", use_container_width=True):
                df_db[~df_db['LBL'].isin(list_hapus)].drop(columns=['LBL']).to_excel(EXCEL_FILE, index=False); st.rerun()
        st.subheader("📊 Database Rekap")
        st.dataframe(df_db.drop(columns=['File_Path', 'LBL'], errors='ignore').iloc[::-1], use_container_width=True, hide_index=True)
        with open(EXCEL_FILE, "rb") as xl:
            st.download_button("📥 Cetak Laporan Excel", xl, file_name=EXCEL_FILE)