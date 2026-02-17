import streamlit as st
import pandas as pd
import easyocr
import cv2
import os
import re
import numpy as np
from datetime import datetime
from PIL import Image
import xlsxwriter

# --- 1. KONFIGURASI & FUNGSI PEMBERSIH ---
EXCEL_FILE = "database_meteran.xlsx"
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def clean_nan(val):
    if pd.isna(val) or str(val).lower() == 'nan':
        return ""
    return str(val)

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'], gpu=False)
reader = load_ocr()

# --- 2. FUNGSI SIMPAN ---
def save_with_image(df_final):
    kolom_utama = ["Tanggal", "Jam", "Nama Meteran", "Angka Meteran", "Foto"]
    df_save = df_final[kolom_utama].copy()
    writer = pd.ExcelWriter(EXCEL_FILE, engine='xlsxwriter')
    df_save.to_excel(writer, index=False, sheet_name='Rekap_Meteran')
    workbook  = writer.book
    worksheet = writer.sheets['Rekap_Meteran']
    worksheet.set_column(4, 4, 35) 
    for i, file_path in enumerate(df_save['Foto']):
        row_num = i + 1
        full_path = os.path.join(UPLOAD_FOLDER, str(file_path))
        if os.path.exists(full_path):
            worksheet.set_row(row_num, 130)
            worksheet.insert_image(row_num, 4, full_path, {
                'x_scale': 0.12, 'y_scale': 0.12, 
                'x_offset': 10, 'y_offset': 10,
                'object_position': 1
            })
    writer.close()

# --- 3. LOGIKA OCR ---
def advanced_pre_process(img_np):
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    return cv2.GaussianBlur(enhanced, (3, 3), 0)

def robust_extract_logic(text_list):
    full_text = " ".join(text_list).upper()
    for unit in ["KWH", "KVARH", "M3/H", "M3", "KVAR"]:
        full_text = full_text.replace(unit, "")
    mapping = {'O': '0', 'D': '0', 'Q': '0', 'B': '8', 'S': '5', 'I': '1', 'L': '1', 'T': '7', 'Z': '2', 'G': '6', 'A': '4'}
    for k, v in mapping.items(): full_text = full_text.replace(k, v)
    full_text = full_text.replace(",", ".")
    pattern = re.findall(r'\d{5,8}(?:\.\d{1,3})?', full_text)
    return max(pattern, key=len) if pattern else "Cek Foto"

# --- 4. UI APLIKASI ---
st.set_page_config(page_title="Input Meteran", layout="wide")
st.title("📟 Input Meteran - PT. Multi Bintang Indonesia")

tab1, tab2 = st.tabs(["📸 Kamera HP", "📁 Galeri"])
source_files = []

with tab1:
    cam_input = st.camera_input("Ambil foto meteran")
    if cam_input: source_files.append(cam_input)

with tab2:
    file_input = st.file_uploader("Upload foto", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
    if file_input: source_files.extend(file_input)

if source_files:
    if 'history' not in st.session_state: st.session_state.history = []
    new_entries = []
    for f in source_files:
        file_id = f.name if hasattr(f, 'name') else f"meter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        if file_id not in st.session_state.history:
            with st.spinner('Menganalisis...'):
                img_path = os.path.join(UPLOAD_FOLDER, file_id)
                with open(img_path, "wb") as sf: sf.write(f.getbuffer())
                img_pil = Image.open(f)
                processed = advanced_pre_process(np.array(img_pil))
                res = reader.readtext(processed, detail=0)
                angka = robust_extract_logic(res)
                
                new_entries.append({
                    "Tanggal": datetime.now().strftime("%d-%m-%Y"),
                    "Jam": datetime.now().strftime("%H:%M"),
                    "Nama Meteran": "Meteran", 
                    "Angka Meteran": angka,
                    "Foto": file_id
                })
                st.session_state.history.append(file_id)
                
    if new_entries:
        df_new = pd.DataFrame(new_entries)
        if os.path.exists(EXCEL_FILE):
            df_old = pd.read_excel(EXCEL_FILE)
            df_final = pd.concat([df_old, df_new], ignore_index=True)
        else:
            df_final = df_new
        save_with_image(df_final) 
        st.rerun()

# --- 5. VERIFIKASI & MANAGEMENT ---
if os.path.exists(EXCEL_FILE):
    df_db = pd.read_excel(EXCEL_FILE)
    if not df_db.empty:
        st.divider()
        st.header("🔍 Verifikasi Data")
        idx, row = df_db.index[-1], df_db.iloc[-1]
        
        c1, c2 = st.columns([1.2, 1])
        with c1:
            foto_path = os.path.join(UPLOAD_FOLDER, str(row['Foto']))
            if os.path.exists(foto_path):
                st.image(foto_path, width=500)
        
        with c2:
            st.warning("Sesuaikan data lapangan:")
            adj_tgl = st.date_input("Tanggal", datetime.now()) # Baris ini untuk Tanggal
            adj_jam = st.text_input("Jam", value=clean_nan(row.get('Jam', ''))) # Baris ini untuk Jam
            
            # Input nama manual tanpa tambahan kata otomatis
            adj_nama = st.text_input("Nama Meteran", value=clean_nan(row.get('Nama Meteran', '')))
            adj_angka = st.text_input("Angka Meteran", value=clean_nan(row.get('Angka Meteran', '')))
            
            if st.button("💾 SIMPAN KE EXCEL", use_container_width=True, type="primary"):
                df_db.at[idx, 'Tanggal'] = adj_tgl.strftime("%d-%m-%Y")
                df_db.at[idx, 'Jam'] = adj_jam
                df_db.at[idx, 'Nama Meteran'] = adj_nama 
                df_db.at[idx, 'Angka Meteran'] = adj_angka
                save_with_image(df_db)
                st.success(f"Tersimpan: {adj_nama}!"); st.rerun()

        st.subheader("📊 Histori Data")
        df_display = df_db.copy().fillna("")
        df_display.insert(0, "Pilih", False)
        edited_df = st.data_editor(
            df_display.drop(columns=['Foto'], errors='ignore').iloc[::-1],
            column_config={"Pilih": st.column_config.CheckboxColumn(default=False)},
            disabled=["Tanggal", "Jam", "Nama Meteran", "Angka Meteran"],
            use_container_width=True,
            key="data_editor"
        )
        selected_rows = edited_df[edited_df["Pilih"] == True]
        if not selected_rows.empty:
            if st.button(f"🗑️ Hapus {len(selected_rows)} Data", use_container_width=True):
                df_db = df_db.drop(selected_rows.index)
                save_with_image(df_db)
                st.warning("Data dihapus!"); st.rerun()

            # --- FITUR DOWNLOAD UNTUK LAPTOP ---
st.divider()
st.subheader("📥 Download Laporan")
if os.path.exists(EXCEL_FILE):
    with open(EXCEL_FILE, "rb") as f:
        st.download_button(
            label="Download Database Meteran (Excel)",
            data=f,
            file_name=f"Rekap_Meteran_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )