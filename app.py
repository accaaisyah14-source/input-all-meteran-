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

# ================= ANTI SSL ERROR =================
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
        'O': '0','D': '0','Q': '0',
        'B': '8','S': '5',
        'I': '1','L': '1',
        'T': '7','Z': '2',
        'G': '6','A': '4'
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
            kolom = ["Tanggal","Jam","Nama Meteran","Angka Meteran","Foto"]
            df_save = df[kolom].copy()

            writer = pd.ExcelWriter(EXCEL_FILE, engine='xlsxwriter')
            df_save.to_excel(writer, index=False, sheet_name='Data')

            workbook  = writer.book
            worksheet = writer.sheets['Data']

            header = workbook.add_format({'bold':True,'border':1})
            for col_num, value in enumerate(df_save.columns):
                worksheet.write(0, col_num, value, header)

            worksheet.set_column(0,4,25)

            for i, file_name in enumerate(df_save['Foto']):
                path = os.path.join(UPLOAD_FOLDER, str(file_name))
                if os.path.exists(path):
                    worksheet.set_row(i+1,120)
                    worksheet.insert_image(i+1,4,path,{'x_scale':0.2,'y_scale':0.2})

            writer.close()
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
            img = img.resize((800,800))

            path = os.path.join(UPLOAD_FOLDER, fname)
            img.save(path)

            processed = advanced_pre_process(np.array(img))
            result = reader.readtext(processed, detail=0)
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

                if nama.strip() == "":
                    st.warning("Nama meteran wajib diisi!")
                else:
                    data_baru = pd.DataFrame([{
                        "Tanggal": tanggal,
                        "Jam": jam,
                        "Nama Meteran": nama,
                        "Angka Meteran": angka_final,
                        "Foto": fname
                    }])

                    if os.path.exists(EXCEL_FILE):
                        df_old = pd.read_excel(EXCEL_FILE, dtype=str)
                        df = pd.concat([df_old, data_baru], ignore_index=True)
                    else:
                        df = data_baru

                    save_data(df)
                    st.success("Data tersimpan!")
                    st.rerun()

# ================= HISTORI =================
if os.path.exists(EXCEL_FILE):
    df = pd.read_excel(EXCEL_FILE, dtype=str)

    if not df.empty:
        st.divider()
        st.subheader("📊 Histori Pencatatan")

        st.dataframe(df.iloc[::-1], use_container_width=True)

        # preview foto
        for i, row in df.iloc[::-1].iterrows():
            with st.expander(f"{row['Tanggal']} | {row['Nama Meteran']}"):
                path = os.path.join(UPLOAD_FOLDER, row["Foto"])
                if os.path.exists(path):
                    st.image(path, width=300)

        # hapus data
        st.divider()
        st.subheader("🗑️ Hapus Data")

        idx = st.selectbox(
            "Pilih data",
            df.index,
            format_func=lambda x: f"{df.loc[x,'Tanggal']} | {df.loc[x,'Nama Meteran']} | {df.loc[x,'Angka Meteran']}"
        )

        if st.button("❌ Hapus Data"):
            df = df.drop(idx)
            save_data(df)
            st.warning("Data dihapus!")
            st.rerun()

        # download
        st.divider()
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)

        st.download_button(
            "📥 Download Excel",
            data=output.getvalue(),
            file_name="data_meteran.xlsx"
        )
