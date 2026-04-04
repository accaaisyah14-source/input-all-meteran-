import time
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
import pytz

st.set_page_config(page_title="Meteran App", initial_sidebar_state="collapsed")

# --- 1. KONFIGURASI & ZONA WAKTU ---
EXCEL_FILE = "database_meteran.xlsx"
UPLOAD_FOLDER = "uploads"
tz_jkt = pytz.timezone('Asia/Jakarta')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def clean_nan(val):
    if pd.isna(val) or str(val).lower() == 'nan':
        return ""
    return str(val)

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)
    
reader = load_reader()
# Tambahkan ini di app.py
if 'reader' not in st.session_state:
    st.session_state.reader = load_reader()
reader = st.session_state.reader

st.title("📸 Input Meteran Utility")
st.write("Silakan ambil foto angka pada meteran.")

# Input Kamera
foto = st.camera_input("Arahkan kamera ke angka")

if foto:
    # Buka foto
    img = Image.open(foto)
    st.image(img, caption="Foto Terambil", use_container_width=True)

    # Proses OCR
    with st.spinner("AI sedang membaca angka..."):
        # Ubah gambar ke format yang dimengerti EasyOCR
        img_np = np.array(img)
        hasil_ocr = reader.readtext(img_np, detail=0)

    # Tampilkan Hasil
    if hasil_ocr:
        angka_deteksi = hasil_ocr[0]
        st.success(f"Angka Terdeteksi: **{angka_deteksi}**")
        
        # Input konfirmasi (takut AI salah baca)
        konfirmasi = st.text_input("Konfirmasi Angka:", value=angka_deteksi)
        
        if st.button("Simpan Data"):
            st.balloons()
            st.success("Data berhasil disimpan (Mode Test)!")
    else:
        st.warning("cek foto.")
        
# --- 2. FUNGSI SIMPAN ---
def save_with_image(df_final):
    max_retries = 5  # Mencoba ulang sampai 5 kali jika file sedang dipakai orang lain
    for attempt in range(max_retries):
        try:
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
            return True # Berhasil simpan, keluar dari loop
        except PermissionError:
            # Jika file terkunci, tunggu 1 detik lalu coba lagi
            time.sleep(1)
        except Exception as e:
            st.error(f"Gagal simpan karena error teknis: {e}")
            break
    return False

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
st.set_page_config(page_title="Input Flow Meter MBI", layout="wide")

# Sidebar untuk Backup Data
st.sidebar.header("⚙️ Recording")
if os.path.exists(EXCEL_FILE):
    with open(EXCEL_FILE, "rb") as f:
        st.sidebar.download_button(
            label="📥 DOWNLOAD BACKUP EXCEL",
            data=f,
            file_name=f"backup_data_{datetime.now(tz_jkt).strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    st.sidebar.warning("⚠️ Download backup ini sebelum melakukan REBOOT agar data tidak hilang.")

st.title("📟 Flow Meter Recording")
st.write(f"🕒 Waktu: {datetime.now(tz_jkt).strftime('%d-%m-%Y %H:%M:%S')} WIB")

tab1, tab2 = st.tabs(["📸 Kamera", "📁 Galeri"])
source_files = []

with tab1:
    cam_input = st.camera_input("Ambil foto meteran")
    if cam_input: source_files.append(cam_input)

with tab2:
    file_input = st.file_uploader("Upload foto", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
    if file_input: source_files.extend(file_input)

if source_files:
    waktu_skrg = datetime.now(tz_jkt)
    if 'history' not in st.session_state: st.session_state.history = []
    new_entries = []
    
    for f in source_files:
        file_id = f.name if hasattr(f, 'name') else f"meter_{waktu_skrg.strftime('%Y%m%d_%H%M%S')}.jpg"
        if file_id not in st.session_state.history:
            with st.spinner('Menganalisis Angka...'):
                img_path = os.path.join(UPLOAD_FOLDER, file_id)
                with open(img_path, "wb") as sf: sf.write(f.getbuffer())
                img_pil = Image.open(f)
                processed = advanced_pre_process(np.array(img_pil))
                res = reader.readtext(processed, detail=0)
                angka = robust_extract_logic(res)
                
                new_entries.append({
                    "Tanggal": waktu_skrg.strftime("%d-%m-%Y"),
                    "Jam": waktu_skrg.strftime("%H:%M"),
                    "Nama Meteran": "", 
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

# --- 5. VERIFIKASI & DATA MANAGEMENT ---
if os.path.exists(EXCEL_FILE):
    df_db = pd.read_excel(EXCEL_FILE)
    if not df_db.empty:
        st.divider()
        st.header("🔍 Verifikasi Data Terakhir")
        idx, row = df_db.index[-1], df_db.iloc[-1]
        
        c1, c2 = st.columns([1.2, 1])
        with c1:
            foto_path = os.path.join(UPLOAD_FOLDER, str(row['Foto']))
            if os.path.exists(foto_path):
                st.image(foto_path, caption="Bukti Foto Lapangan", width=500)
        
        with c2:
            st.info("Pastikan data di bawah sudah benar:")
            adj_tgl = st.date_input("Tanggal", datetime.now(tz_jkt))
            adj_jam = st.text_input("Jam", value=clean_nan(row.get('Jam', '')))
            adj_nama = st.text_input("Nama Meteran", value=clean_nan(row.get('Nama Meteran', '')))
            adj_angka = st.text_input("Angka Meteran (Edit jika salah)", value=clean_nan(row.get('Angka Meteran', '')))
            
            if st.button("✅ KONFIRMASI & SIMPAN", use_container_width=True, type="primary"):
                df_db['Nama Meteran'] = df_db['Nama Meteran'].astype(str)
                df_db['Angka Meteran'] = df_db['Angka Meteran'].astype(str)
                df_db['Tanggal'] = df_db['Tanggal'].astype(str)
                df_db['Jam'] = df_db['Jam'].astype(str)

                df_db.at[idx, 'Tanggal'] = adj_tgl.strftime("%d-%m-%Y")
                df_db.at[idx, 'Jam'] = str(adj_jam)
                df_db.at[idx, 'Nama Meteran'] = str(adj_nama) # <--- PASTIKAN BARIS INI ADA
                df_db.at[idx, 'Angka Meteran'] = str(adj_angka)
                
                save_with_image(df_db)
                st.success(f"Data {adj_nama} Berhasil Diverifikasi!"); 
                st.rerun()

        st.subheader("📊 Histori Pencatatan (Terbaru di Atas)")
        df_display = df_db.copy().fillna("")
        df_display.insert(0, "Pilih", False)
        
        # Tampilkan data terbalik (terbaru di atas)
        edited_df = st.data_editor(
            df_display.drop(columns=['Foto'], errors='ignore').iloc[::-1],
            column_config={"Pilih": st.column_config.CheckboxColumn(default=False)},
            disabled=["Tanggal", "Jam", "Nama Meteran", "Angka Meteran"],
            use_container_width=True,
            key="data_editor"
        )
        
        selected_rows = edited_df[edited_df["Pilih"] == True]
        if not selected_rows.empty:
            if st.button(f"🗑️ Hapus {len(selected_rows)} Data Terpilih", use_container_width=True):
                df_db = df_db.drop(selected_rows.index)
                save_with_image(df_db)
                st.warning("Data berhasil dihapus!"); st.rerun()
