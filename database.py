import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 🔐 โครงสร้างการเชื่อมต่อ Supabase ---
# ดึงค่า URL และ KEY จาก st.secrets (ซึ่งจะดึงจาก .streamlit/secrets.toml ในเครื่อง หรือ Streamlit Cloud)
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    # ค่าเริ่มต้นสำหรับทดสอบ หากยังไม่ได้ตั้งค่าใน Secrets
    SUPABASE_URL = "https://your-project-id.supabase.co"
    SUPABASE_KEY = "your-anon-key"

# ตรวจสอบว่ามีค่าเชื่อมต่อครบถ้วนหรือไม่
if SUPABASE_URL == "https://your-project-id.supabase.co" or not SUPABASE_URL:
    st.warning("⚠️ กรุณาตั้งค่า Supabase URL และ Key ในไฟล์ `.streamlit/secrets.toml` ก่อนใช้งานครับ")
    supabase = None
else:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"🔴 เชื่อมต่อ Supabase ล้มเหลว: {e}")
        supabase = None

# --- 🗺️ แผนผัง Primary Key ของแต่ละตาราง ---
# PostgreSQL จำเป็นต้องรู้ว่าฟิลด์ไหนเป็น Key หลักสำหรับการอัปเดตหรือลบข้อมูล
PK_MAP = {
    "Liner": "Liner ID",
    "Port_Loading": "PL ID",
    "Port_Discharge": "PD ID",
    "Container_Type": "CT ID",
    "Charge Item": "Charge ID",
    "Tax (%)": "Tax ID",
    "VAT (%)": "VAT ID",
    "Currency": "Currency ID",
    "Sender": "Sender ID",
    "Customer": "Customer ID",
    "Booking_Header": "Booking ID",
    "Booking_Detail": "Detail ID",
    "Invoice_Header": "Invoice ID",
    "Invoice_Detail": "Invoice Detail ID",
    "Receipt_Header": "Receipt ID",
    "Job_Costing": "Costing ID",
    "Bank_Account": "Bank ID"
}

# --- 🌀 ฟังก์ชันหลักที่ทำงานร่วมกับ Streamlit (เหมือนโครงสร้างเดิมของท่าน) ---

# --- 🌀 ระบบ Cache แยกตามตาราง (Sheet-Specific Caching) ---
def _fetch_table_raw(table_name):
    if supabase is None:
        return pd.DataFrame()
    try:
        response = supabase.table(table_name).select("*").execute()
        data = response.data
        if not data:
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        pk_col = PK_MAP.get(table_name)
        if pk_col and pk_col in df.columns:
            df['airtable_record_id'] = df[pk_col]
        else:
            df['airtable_record_id'] = df.index.astype(str)
            
        return df
    except Exception as e:
        st.error(f"Error ดึงข้อมูลจาก {table_name}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Customer(): return _fetch_table_raw("Customer")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Booking_Header(): return _fetch_table_raw("Booking_Header")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Booking_Detail(): return _fetch_table_raw("Booking_Detail")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Invoice_Header(): return _fetch_table_raw("Invoice_Header")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Invoice_Detail(): return _fetch_table_raw("Invoice_Detail")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Receipt_Header(): return _fetch_table_raw("Receipt_Header")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Job_Costing(): return _fetch_table_raw("Job_Costing")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Liner(): return _fetch_table_raw("Liner")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Port_Loading(): return _fetch_table_raw("Port_Loading")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Port_Discharge(): return _fetch_table_raw("Port_Discharge")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Container_Type(): return _fetch_table_raw("Container_Type")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Charge_Item(): return _fetch_table_raw("Charge Item")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Tax(): return _fetch_table_raw("Tax (%)")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_VAT(): return _fetch_table_raw("VAT (%)")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Currency(): return _fetch_table_raw("Currency")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Sender(): return _fetch_table_raw("Sender")

@st.cache_data(ttl=300, show_spinner=False)
def _cache_Bank_Account(): return _fetch_table_raw("Bank_Account")

CACHE_MAP = {
    "Customer": _cache_Customer,
    "Booking_Header": _cache_Booking_Header,
    "Booking_Detail": _cache_Booking_Detail,
    "Invoice_Header": _cache_Invoice_Header,
    "Invoice_Detail": _cache_Invoice_Detail,
    "Receipt_Header": _cache_Receipt_Header,
    "Job_Costing": _cache_Job_Costing,
    "Liner": _cache_Liner,
    "Port_Loading": _cache_Port_Loading,
    "Port_Discharge": _cache_Port_Discharge,
    "Container_Type": _cache_Container_Type,
    "Charge Item": _cache_Charge_Item,
    "Tax (%)": _cache_Tax,
    "VAT (%)": _cache_VAT,
    "Currency": _cache_Currency,
    "Sender": _cache_Sender,
    "Bank_Account": _cache_Bank_Account
}

def get_data_from_sheet(table_name):
    """ดึงข้อมูลจากตารางใน Supabase มาแปลงเป็น DataFrame (มีระบบ Cache 5 นาทีแยกตามตาราง)"""
    if table_name in CACHE_MAP:
        return CACHE_MAP[table_name]()
    return _fetch_table_raw(table_name)

def clear_sheet_cache(table_name=None):
    """ล้าง Cache เฉพาะตารางที่กำหนด หากไม่ระบุจะล้างทั้งหมด"""
    if table_name and table_name in CACHE_MAP:
        CACHE_MAP[table_name].clear()
    else:
        for fn in CACHE_MAP.values():
            fn.clear()


def generate_next_id(table_name, id_col, prefix):
    """ฟังก์ชันคำนวณรหัส ID ถัดไปอัตโนมัติ (เช่น BK0001 -> BK0002)"""
    df = get_data_from_sheet(table_name)
    if df.empty or id_col not in df.columns:
        return f"{prefix}0001"
        
    max_num = 0
    for val in df[id_col].dropna():
        val_str = str(val).strip()
        if val_str.startswith(prefix):
            try:
                num = int(val_str.replace(prefix, ''))
                if num > max_num:
                    max_num = num
            except:
                pass
    return f"{prefix}{(max_num + 1):04d}"

def generate_next_year_id(table_name, id_col, prefix):
    """ฟังก์ชันคำนวณรหัส ID แบบรีเซ็ตรายปี (เช่น ROC260001, REC260001)"""
    import datetime
    df = get_data_from_sheet(table_name)
    current_year_yy = str(datetime.date.today().year)[2:]
    prefix_yy = f"{prefix}{current_year_yy}"
    
    if df.empty or id_col not in df.columns:
        return f"{prefix_yy}0001"
        
    max_num = 0
    for val in df[id_col].dropna():
        val_str = str(val).strip()
        if val_str.startswith(prefix_yy):
            try:
                # แยกเอาเฉพาะตัวเลขรันนิ่งหลัง prefix และปี
                num_str = val_str[len(prefix_yy):]
                num = int(num_str)
                if num > max_num:
                    max_num = num
            except:
                pass
    return f"{prefix_yy}{(max_num + 1):04d}"

def append_record(table_name, record_dict):
    """บันทึกข้อมูลใหม่ 1 แถวลง Supabase"""
    if supabase is None:
        raise Exception("ยังไม่ได้เชื่อมต่อกับ Supabase")
        
    try:
        # กรองค่าว่างออกเพื่อให้ PostgreSQL ใช้ค่า Default หรือ Null ได้อย่างถูกต้อง
        clean_dict = {k: v for k, v in record_dict.items() if v is not None and str(v).strip() != ""}
        
        # บันทึกข้อมูล
        response = supabase.table(table_name).insert(clean_dict).execute()
        
        # 🌟 ล้าง Cache เฉพาะตารางที่มีการแก้ไข เพื่อให้ดึงข้อมูลใหม่มาแสดงทันที
        clear_sheet_cache(table_name)
        return response.data
    except Exception as e:
        raise Exception(f"Supabase Insert Error ({table_name}): {e}")

def update_record(table_name, record_id, record_dict):
    """แก้ไขข้อมูลใน Supabase"""
    if supabase is None:
        raise Exception("ยังไม่ได้เชื่อมต่อกับ Supabase")
        
    try:
        pk_col = PK_MAP.get(table_name)
        if not pk_col:
            raise Exception(f"ไม่พบคอลัมน์ Primary Key สำหรับตาราง {table_name}")
            
        clean_dict = {k: v for k, v in record_dict.items() if v is not None and str(v).strip() != ""}
        
        # อัปเดตข้อมูลโดยค้นหาจาก Primary Key
        response = supabase.table(table_name).update(clean_dict).eq(pk_col, record_id).execute()
        
        # 🌟 ล้าง Cache เฉพาะตาราง
        clear_sheet_cache(table_name)
        return response.data
    except Exception as e:
        raise Exception(f"Supabase Update Error ({table_name}): {e}")

def append_records_bulk(table_name, records_list):
    """บันทึกข้อมูลเป็นกลุ่ม (หลายแถวพร้อมกัน)"""
    if supabase is None:
        raise Exception("ยังไม่ได้เชื่อมต่อกับ Supabase")
        
    try:
        clean_records = []
        for r in records_list:
            clean_r = {k: v for k, v in r.items() if v is not None and str(v).strip() != ""}
            clean_records.append(clean_r)
            
        if clean_records:
            response = supabase.table(table_name).insert(clean_records).execute()
            
        # 🌟 ล้าง Cache เฉพาะตาราง
        clear_sheet_cache(table_name)
    except Exception as e:
        raise Exception(f"Supabase Bulk Insert Error ({table_name}): {e}")

def delete_records_bulk(table_name, record_ids):
    """ลบข้อมูลเป็นกลุ่ม"""
    if supabase is None:
        raise Exception("ยังไม่ได้เชื่อมต่อกับ Supabase")
        
    try:
        pk_col = PK_MAP.get(table_name)
        if not pk_col:
            raise Exception(f"ไม่พบคอลัมน์ Primary Key สำหรับตาราง {table_name}")
            
        if record_ids:
            response = supabase.table(table_name).delete().in_(pk_col, record_ids).execute()
            
        # 🌟 ล้าง Cache เฉพาะตาราง
        clear_sheet_cache(table_name)
    except Exception as e:
        raise Exception(f"Supabase Bulk Delete Error ({table_name}): {e}")
