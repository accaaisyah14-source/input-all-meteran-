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
import hashlib

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
tz_jkt = pytz.timezone("Asia/Jakarta")

LIST_METERAN = [
    "1. DEEPWELL 1 AQUADUCT SIPA",
    "2. DEEPWELL 2 FISHPOND SIPA",
    "3. DEEPWELL 3 AWANG-AWANG SIPA",
    "4. STATIC WATER LEVEL (JTL)",
    "5. DYNAMIC WATER LEVEL (AWG)",
    "6. DEEPWELL 4 JATILANGKUNG PIPA",
    "7. STATIC WATER LEVEL (JTL)",
    "8. DYNAMIC WATER LEVEL (JTL)",
    "9. DEEPWELL 5 RIVER SIPA",
    "10. DEEPWELL 6 FRONT OFFICE SIPA",
    "11. DEEPWELL 7 TEMPURAN SIPA",
    "12. STATIC WATER LEVEL (TPR)",
    "13. DYNAMIC WATER LEVEL (TPR)",
    "14. DEEPWELL 1 AQUADUCT MBI",
    "15. DEEPWELL 2 FISHPOND SIPA",
    "16. DEEPWELL 3 AWANG-AWANG SIPA",
    "17. DEEPWELL 4 JATILANGKUNG MBI",
    "18. DEEPWELL 5 RIVER MBI",
    "19. DEEPWELL 6 FRONT OFFICE MBI",
    "20. DEEPWELL 7 TEMPURAN MBI",
    "21. DEEPWELL STORAGE TANK",
    "22. CATION 1",
    "23. CATION 2",
    "24. MM MIX TO PWT",
    "25. FLOW TO PWT",
    "26. AFTER ACF",
    "27. SOFTENER OUTLET",
    "28. MM MIX TO SWT",
    "29. FLOW TO FWT",
    "30. FWT TO CONSUMER",
    "31. SOFT WATER TO CONSUMER",
    "32. DEMIN WATER",
    "33. BOILER MAKE UP WATER",
    "34. CO2 COOLING WATER",
    "35. NH3 EVAP CONDENSOR",
    "36. ETHANOL MIXING WATER",
    "37. CO2 SCRUBBER TANK",
    "38. WWTP WATER CONS",
    "39. SOFT WATER FOR CHAIN LUBRICANT",
    "40. BOTTLE WASHER",
    "41. CRATE WASHER",
    "42. PASTEURIZER",
    "43. FILLERS & VACUUM PUMPS",
    "44. RACKING PLANT",
    "45. SODA STATION",
    "46. PACKAGING MAIN LINE",
    "47. CELLAR FLOOR",
    "48. CO2 FOAM CATCHER 1",
    "49. CO2 FOAM CATCHER 2",
    "50. FILTRATION & BREWHOUSE MAIN LINE",
    "51. YEAST TANK",
    "52. PVPP KIESELGUHR TANKS",
    "53. COLD & HOT WATER TANKS",
    "54. MAIN LABORATORY",
    "55. SANITARY WATER MAIN LINE",
    "56. FIRE FIGHTING",
    "57. CORE TEAM WC",
    "58. BOTTLING WC",
    "59. FULL STORE",
    "60. EMPTY STORE",
    "61. FRONT OFFICE",
    "62. PARKING LODGE",
    "63. WELFARE + CLINIC",
    "64. MUSHOLA",
    "65. CANTEEN + PORTER LODGE",
    "66. ENGINE ROOM WC",
    "67. BREWHOUSE WC",
    "68. SILO WC",
    "69. BUNKER FLOW METER",
    "70. BOILER 1 FUEL METER",
    "71. BOILER 2 FUEL METER",
    "72. FORKLIFT FUEL (PICK LIST)",
    "73. CORRECTOR GAS METER",
    "74. CANTEEN GAS METER",
    "75. BOILER 1 STEAM METER",
    "76. BOILER 1 FEED WATER METER",
    "77. BOILER 2 STEAM METER",
    "78. BOILER 2 FEED WATER METER",
    "79. PACKAGING STEAM METER",
    "80. PACKAGING CONDENSATE METER",
    "81. BREWING STEAM METER",
    "82. BREWING CONDENSATE METER",
    "83. BOILER BLOWDOWN METER",
    "84. CO2 RECUPERATION",
    "85. STORAGE TANK 1 VOLUME",
    "86. STORAGE TANK 2 VOLUME",
    "87. PACKAGING TOTALIZER",
    "88. BREWING TOTALIZER",
    "89. CO2 PURCHASE",
    "90. CO2 SOLD",
    "91. CO2 BOTTLED",
    "92. INCOMING CAUSTIC METER",
    "93. PACKAGING CAUSTIC METER",
    "94. BREWING CAUSTIC METER",
    "95. WTP CAUSTIC METER",
    "96. PASTEURIZER STEAM",
    "97. BOTTLE WASHER",
    "98. WK 1 STEAM METER",
    "99. WK 2 STEAM METER",
    "100. WTP STEAM METER",
    "101. RACKING PLANT",
    "102. WTP CAUSTIC METER",
    "103. PDAM MBI",
    "104. PDAM DEPAN",
    "105. ACF 1 CHRIWA",
    "106. ACF 2 CHRIWA",
    "107. FWS CIP",
    "108. FWS PROD",
    "109. STEAM",
    "110. STEAM TO PASTEUR",
    "111. FW TO PASTEUR",
    "112. STEAM CIP",
    "113. STEAM MBI",
    "114. STEAM BECIS",
    "115. FACT CIP BMF",
    "116. PROD ALDOX",
    "117. FACT TANK II",
    "118. SPRAY BALL MASTUN",
    "119. SPRAY BALL WPOOL",
    "120. STEAM BREWING",
    "121. RAW",
    "122. PWT",
    "123. FWT",
    "124. CO2 BALOON"
]

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= SESSION =================
if "last_saved" not in st.session_state:
    st.session_state.last_saved = None

# ================= OCR =================
@st.cache_resource
def load_reader():
    return easyocr.Reader(["en"], gpu=False)

reader = load_reader()


def robust_extract_logic(text_list):
    full_text = " ".join(text_list).upper()

    for unit in ["KWH", "KVARH", "M3/H", "M3", "KVAR"]:
        full_text = full_text.replace(unit, "")

    mapping = {
        "O": "0", "D": "0", "Q": "0",
        "B": "8", "S": "5",
        "I": "1", "L": "1",
        "T": "7", "Z": "2",
        "G": "6", "A": "4"
    }

    for salah, benar in mapping.items():
        full_text = full_text.replace(salah, benar)

    full_text = full_text.replace(",", ".")
    pattern = re.findall(r"\d{5,8}(?:\.\d{1,3})?", full_text)

    return max(pattern, key=len) if pattern else "Cek Foto"


@st.cache_data(show_spinner=False)
def process_image(file_bytes):
    """
    OCR hanya dijalankan satu kali untuk file yang sama.
    Saat pengguna memilih nama atau mengedit angka, hasil OCR diambil dari cache.
    """
    with Image.open(io.BytesIO(file_bytes)) as opened_image:
        image = opened_image.convert("RGB").copy()

    image.thumbnail((800, 800))

    image_np = np.array(image)
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    processed = cv2.GaussianBlur(enhanced, (3, 3), 0)

    result = reader.readtext(processed, detail=0)
    angka = robust_extract_logic(result)

    return image, angka


# ================= EXCEL LOCK =================
def wait_for_lock(lock_file, timeout=15):
    mulai = time.time()

    while os.path.exists(lock_file):
        if time.time() - mulai > timeout:
            try:
                os.remove(lock_file)
            except OSError:
                pass
            break
        time.sleep(0.2)


def append_data_safely(data_baru):
    """
    Lock mencakup proses membaca dan menulis Excel,
    sehingga data dari dua pengguna tidak mudah saling menimpa.
    """
    lock_file = EXCEL_FILE + ".lock"
    wait_for_lock(lock_file)

    try:
        with open(lock_file, "w", encoding="utf-8"):
            pass

        if os.path.exists(EXCEL_FILE):
            df_old = pd.read_excel(EXCEL_FILE)
        else:
            df_old = pd.DataFrame()

        df_baru = pd.concat([df_old, data_baru], ignore_index=True)

        with pd.ExcelWriter(EXCEL_FILE, engine="xlsxwriter") as writer:
            df_baru.to_excel(writer, index=False)

    finally:
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except OSError:
                pass


def save_dataframe_safely(df):
    lock_file = EXCEL_FILE + ".lock"
    wait_for_lock(lock_file)

    try:
        with open(lock_file, "w", encoding="utf-8"):
            pass

        with pd.ExcelWriter(EXCEL_FILE, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)

    finally:
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except OSError:
                pass


# ================= UI =================
st.title("📟 Flow Meter Recording")

# Satu foto setiap kali agar proses lebih ringan dan tidak membingungkan pengguna.
uploaded_file = st.file_uploader(
    "📁 Upload Foto Meteran",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=False
)

# ================= PROCESS =================
if uploaded_file is not None:
    now = datetime.now(tz_jkt)
    file_bytes = uploaded_file.getvalue()

    try:
        img, angka = process_image(file_bytes)

        # Nama file unik mencegah foto dengan nama sama saling menimpa.
        file_hash = hashlib.md5(file_bytes).hexdigest()[:10]
        ext = os.path.splitext(uploaded_file.name)[1].lower() or ".jpg"
        fname = f"{datetime.now(tz_jkt).strftime('%Y%m%d_%H%M%S')}_{file_hash}{ext}"
        path = os.path.join(UPLOAD_FOLDER, fname)

        if not os.path.exists(path):
            img.save(path)

    except Exception as e:
        st.error(f"Gagal membaca atau memproses gambar: {e}")
        st.stop()

    st.divider()
    col1, col2 = st.columns([1, 1])

    with col1:
        st.image(img, caption="Foto Meteran", use_column_width=True)

    with col2:
        tanggal = st.text_input(
            "Tanggal",
            value=now.strftime("%d-%m-%Y"),
            key=f"tgl_{file_hash}"
        )

        jam = st.text_input(
            "Jam",
            value=now.strftime("%H:%M"),
            key=f"jam_{file_hash}"
        )

        nama = st.selectbox(
            "Pilih Nama Meteran",
            options=LIST_METERAN,
            index=None,
            placeholder="Ketik atau pilih nama meteran...",
            key=f"nama_{file_hash}"
        )

        angka_final = st.text_input(
            "Angka Meteran (Edit jika salah)",
            value=str(angka),
            key=f"angka_{file_hash}"
        )

        if st.button(
            "✅ KONFIRMASI & SIMPAN",
            key=f"save_{file_hash}",
            type="primary"
        ):
            if not nama:
                st.warning("Nama meteran wajib dipilih!")

            elif angka_final.strip() == "":
                st.warning("Angka meteran masih kosong!")

            else:
                angka_bersih = angka_final.strip().replace(",", ".")

                try:
                    angka_float = float(angka_bersih)
                except ValueError:
                    st.warning("Format angka salah. Gunakan angka, misalnya 12345 atau 12345.67.")
                else:
                    unique_key = f"{tanggal}_{jam}_{nama}_{angka_float}"

                    if st.session_state.last_saved == unique_key:
                        st.warning("Data tersebut sudah tersimpan!")
                    else:
                        try:
                            data_baru = pd.DataFrame([{
                                "Tanggal": tanggal,
                                "Jam": jam,
                                "Nama Meteran": nama,
                                "Angka Meteran": angka_float,
                                "Foto": fname
                            }])

                            append_data_safely(data_baru)
                            st.session_state.last_saved = unique_key
                            st.success("Data berhasil tersimpan!")
                            st.rerun()

                        except Exception as e:
                            st.error(f"Gagal menyimpan data: {e}")


# ================= HISTORI =================
if os.path.exists(EXCEL_FILE):
    try:
        df = pd.read_excel(EXCEL_FILE)
    except Exception as e:
        st.error(f"Database Excel tidak dapat dibaca: {e}")
        df = pd.DataFrame()

    if not df.empty:
        st.divider()
        st.subheader("📊 Histori Pencatatan")

        # Tampilkan maksimal 100 catatan terbaru agar halaman tetap ringan.
        df_tampil = (
            df.drop(columns=["Foto"], errors="ignore")
              .iloc[::-1]
              .head(100)
        )

        st.dataframe(
            df_tampil,
            use_container_width=True,
            hide_index=True
        )

        with st.expander("🗑️ Hapus Data"):
            df_reset = df.reset_index(drop=True)

            pilih = st.multiselect(
                "Pilih data yang ingin dihapus",
                options=df_reset.index.tolist(),
                format_func=lambda x: (
                    f"{df_reset.loc[x, 'Tanggal']} | "
                    f"{df_reset.loc[x, 'Nama Meteran']} | "
                    f"{df_reset.loc[x, 'Angka Meteran']}"
                )
            )

            if st.button("❌ Hapus Data Terpilih"):
                if not pilih:
                    st.warning("Pilih data terlebih dahulu!")
                else:
                    try:
                        foto_hapus = []

                        if "Foto" in df_reset.columns:
                            foto_hapus = (
                                df_reset.loc[pilih, "Foto"]
                                .dropna()
                                .astype(str)
                                .tolist()
                            )

                        df_sisa = df_reset.drop(index=pilih).reset_index(drop=True)
                        save_dataframe_safely(df_sisa)

                        for nama_foto in foto_hapus:
                            foto_path = os.path.join(UPLOAD_FOLDER, nama_foto)
                            if os.path.exists(foto_path):
                                try:
                                    os.remove(foto_path)
                                except OSError:
                                    pass

                        st.success(f"{len(pilih)} data berhasil dihapus!")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Gagal menghapus data: {e}")

        # Pembuatan file unduhan hanya dilakukan saat bagian ini dibuka.
        with st.expander("📥 Download Data"):
            output = io.BytesIO()
            df_download = df.drop(columns=["Foto"], errors="ignore")

            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_download.to_excel(writer, index=False)

            st.download_button(
                label="📥 Download Excel",
                data=output.getvalue(),
                file_name="data_meteran.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
