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
    return easyocr.Reader(['en'], gpu=False)

reader = load_reader()

def advanced_pre_process(img_np):
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    return cv2.GaussianBlur(enhanced, (3, 3), 0)

def robust_extract_logic(text_list):
    full_text = " ".join(text_list).upper()

    for unit in ["KWH", "KVARH", "M3/H", "M3", "KVAR"]:
        full_text = full_text.replace(unit, "")

    mapping = {
        'O': '0', 'D': '0', 'Q': '0',
        'B': '8', 'S': '5',
        'I': '1', 'L': '1',
        'T': '7', 'Z': '2',
        'G': '6', 'A': '4'
    }

    for k, v in mapping.items():
        full_text = full_text.replace(k, v)

    full_text = full_text.replace(",", ".")

    pattern = re.findall(r'\d{5,8}(?:\.\d{1,3})?', full_text)

    return max(pattern, key=len) if pattern else "Cek Foto"

# ================= SAVE EXCEL =================
def save_data(df):
    import xlsxwriter

    for _ in range(3):
        try:
            kolom = ["Tanggal", "Jam", "Nama Meteran", "Angka Meteran", "Foto"]
            df_save = df[kolom].copy()

            df_save["Angka Meteran"] = df_save["Angka Meteran"].astype(str)

            writer = pd.ExcelWriter(EXCEL_FILE, engine='xlsxwriter')
            df_save.to_excel(writer, index=False, sheet_name='Data Meteran')

            workbook  = writer.book
            worksheet = writer.sheets['Data Meteran']

            # header format
            header_format = workbook.add_format({
                'bold': True,
                'align': 'center',
                'border': 1
            })

            for col_num, value in enumerate(df_save.columns):
                worksheet.write(0, col_num, value, header_format)

            # column width
            worksheet.set_column(0, 0, 15)
            worksheet.set_column(1, 1, 10)
            worksheet.set_column(2, 2, 25)
            worksheet.set_column(3, 3, 20)
            worksheet.set_column(4, 4, 35)

            # insert image
            for i, file_name in enumerate(df_save['Foto']):
                row = i + 1
                path = os.path.join(UPLOAD_FOLDER, str(file_name))

                if os.path.exists(path):
                    worksheet.set_row(row, 120)
                    worksheet.insert_image(row, 4, path, {
                        'x_scale': 0.15,
                        'y_scale': 0.15
                    })

            writer.close()
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

                processed = advanced_pre_process(np.array(img))
                result = reader.readtext(processed, detail=0)

                angka = robust_extract_logic(result)

            except:
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

        save_data(df)
        st.success("Data tersimpan!")
        st.rerun()

# ================= TAMPIL DATA =================
if os.path.exists(EXCEL_FILE):
    df = pd.read_excel(EXCEL_FILE, dtype=str)

    if not df.empty:
        st.divider()
        st.subheader("📊 Histori Pencatatan")

        st.dataframe(df.iloc[::-1], use_container_width=True)

        # ================= HAPUS DATA =================
        st.divider()
        st.subheader("🗑️ Hapus Data")

        df_reset = df.reset_index()

        selected_index = st.selectbox(
            "Pilih data",
            df_reset.index,
            format_func=lambda x: f"{df_reset.loc[x,'Tanggal']} | {df_reset.loc[x,'Nama Meteran']} | {df_reset.loc[x,'Angka Meteran']}"
        )

        if st.button("❌ Hapus Data"):
            df = df.drop(selected_index)
            save_data(df)
            st.warning("Data berhasil dihapus!")
            st.rerun()

        # ================= DOWNLOAD EXCEL =================
        st.divider()

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)

        st.download_button(
            label="📥 Download Excel",
            data=output.getvalue(),
            file_name="data_meteran.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
