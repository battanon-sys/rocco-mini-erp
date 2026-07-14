import streamlit as st
import datetime
import pandas as pd
import time
import io
import altair as alt
from decimal import Decimal, ROUND_HALF_UP
from fpdf import FPDF
import database
import importlib
# ตรวจสอบและอัปเดตโมดูล database ในหน่วยความจำหากเป็นเวอร์ชันเก่าก่อนทำการ import ฟังก์ชันใหม่
if not hasattr(database, 'clear_sheet_cache') or not hasattr(database, '_cache_Customer'):
    importlib.reload(database)
from database import (generate_next_id, generate_next_year_id, get_data_from_sheet, 
                      append_record, update_record, 
                      append_records_bulk, delete_records_bulk, clear_sheet_cache)

st.set_page_config(page_title="ROCCO MINI ERP", layout="wide") 

# --- Custom Styling for Premium Look ---
st.markdown("""
<style>
    .reportview-container {
        background: #f4f6f9;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    h1 {
        color: #1c4587;
        font-family: 'Outfit', 'Segoe UI', sans-serif;
        font-weight: 700;
    }
    h2, h3, h4 {
        color: #2c3e50;
        font-family: 'Outfit', 'Segoe UI', sans-serif;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #f1f3f5;
        border-radius: 4px 4px 0px 0px;
        padding: 10px 20px;
        color: #495057;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e9ecef;
        color: #1c4587;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1c4587 !important;
        color: white !important;
    }
    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #e9ecef;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
</style>
""", unsafe_allow_html=True)

st.title("ROCCO MINI ERP - ระบบจัดการข้อมูลการขนส่ง (Supabase Cloud Edition)")

# 1. นิยาม Config ของ Master Data
master_configs = [
    {'name': 'Liner', 'sheet': 'Liner', 'id': 'Liner ID', 'pre': 'L', 'cols': ['Liner Name', 'Liner Short Name', 'Liner Tax ID']},
    {'name': 'Port Loading', 'sheet': 'Port_Loading', 'id': 'PL ID', 'pre': 'PL', 'cols': ['Port Name', 'Paperless Code']},
    {'name': 'Port Discharge', 'sheet': 'Port_Discharge', 'id': 'PD ID', 'pre': 'PD', 'cols': ['Port Name', 'Country']},
    {'name': 'Container Type', 'sheet': 'Container_Type', 'id': 'CT ID', 'pre': 'CT', 'cols': ['Container Type']},
    {'name': 'Charge Item', 'sheet': 'Charge Item', 'id': 'Charge ID', 'pre': 'CI', 'cols': ['Charge Item']},
    {'name': 'Tax (%)', 'sheet': 'Tax (%)', 'id': 'Tax ID', 'pre': 'T', 'cols': ['Tax (%)']},
    {'name': 'VAT (%)', 'sheet': 'VAT (%)', 'id': 'VAT ID', 'pre': 'V', 'cols': ['VAT (%)']},
    {'name': 'Currency (สกุลเงิน)', 'sheet': 'Currency', 'id': 'Currency ID', 'pre': 'CU', 'cols': ['Currency']},
    {'name': 'Sender', 'sheet': 'Sender', 'id': 'Sender ID', 'pre': 'S', 'cols': ['Sender Name', 'Sender Phone']}
]

# --- 🛡️ Helper Functions ---
def round_half_up(val, decimals=2):
    if val is None or val == "": return 0.0
    try:
        if isinstance(val, float) and val != val: return 0.0
        d = Decimal(str(val))
        formatter = Decimal('0.' + '0' * decimals) if decimals > 0 else Decimal('0')
        return float(d.quantize(formatter, rounding=ROUND_HALF_UP))
    except:
        try: return float(val)
        except: return 0.0

def safe_str(val): 
    if val is None: return ""
    if isinstance(val, list): val = val[0] if len(val) > 0 else ""
    try:
        if pd.isna(val): return ""
    except: pass
    return str(val).strip()

def safe_float(val, default=0.0):
    if val is None or val == "": return default
    if isinstance(val, list): val = val[0] if len(val) > 0 else default
    try:
        if pd.isna(val): return default
    except: pass
    try: return float(val)
    except: return default

def p_date(val):
    v = safe_str(val)
    if not v or v in ["nan", "NaT", "None"]: return None
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):
        try: return datetime.datetime.strptime(v, fmt).date()
        except: pass
    return None

def p_time(val):
    v = safe_str(val)
    if not v or v in ["nan", "NaT", "None"]: return None
    try: return datetime.datetime.strptime(v, '%H:%M').time()
    except: pass
    try: return datetime.datetime.strptime(v, '%H:%M:%S').time()
    except: pass
    return None

def fmt_date(d): return d.strftime('%Y-%m-%d') if d else None
def fmt_time(t): return t.strftime('%H:%M') if t else None

def format_doc_date(val):
    """แปลงวันที่ให้อยู่ในรูปแบบ DD-MM-YYYY (เช่น 09-07-2026) สำหรับแสดงในเอกสาร PDF"""
    if val is None:
        return ""
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.strftime('%d-%m-%Y')
    v = safe_str(val).split("T")[0].split(" ")[0].strip()
    if not v or v in ["nan", "NaT", "None", ""]:
        return ""
    d = p_date(v)
    if d:
        return d.strftime('%d-%m-%Y')
    parts = v.split("-") if "-" in v else (v.split("/") if "/" in v else [])
    if len(parts) == 3:
        if len(parts[0]) == 4:
            try: return f"{int(parts[2]):02d}-{int(parts[1]):02d}-{parts[0]}"
            except: pass
        elif len(parts[2]) == 4:
            try: return f"{int(parts[0]):02d}-{int(parts[1]):02d}-{parts[2]}"
            except: pass
    return v

def safe_bool(val):
    if val is True: return True
    if val is None: return False
    if isinstance(val, list): return val[0] if len(val) > 0 else False
    if isinstance(val, str): return val.strip().lower() in ['true', '1', 'yes', 'y', 'checked']
    return False

# -------------------------------------------------------------------------
# 🛠️ ฟังก์ชันหน้ากระดาษ Booking Confirmation PDF
def create_booking_confirmation_pdf(bk_row, df_bd, df_sender):
    def clean_val(val): return safe_str(val).replace("'", "")
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    try:
        pdf.add_font("THSarabun", style="", fname="THSarabunNew.ttf", uni=True)
        pdf.add_font("THSarabun", style="B", fname="THSarabunNew Bold.ttf", uni=True)
        has_font = True
    except: has_font = False

    # Override set_font dynamically to handle missing fonts gracefully
    original_set_font = pdf.set_font
    def safe_set_font(family, style="", size=0, *args, **kwargs):
        if family == "THSarabun" and not has_font:
            family = "helvetica"
        if family.lower() == "arial":
            family = "helvetica"
        return original_set_font(family, style, size, *args, **kwargs)
    pdf.set_font = safe_set_font
    pdf.set_font("helvetica", "B", 12)

    try: pdf.image("logo.png", x=150, y=10, w=45)
    except: pass 
        
    if has_font: pdf.set_font("THSarabun", "B", 18)
    pdf.set_text_color(28, 69, 135)
    pdf.cell(100, 8, "ROCCO (THAILAND) CO., LTD.", ln=True)
    if has_font: pdf.set_font("THSarabun", "B", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(100, 6.5, "90/123 MOO 15, PLEX-BANGNA, BANGNA-TRAD ROAD,", ln=True)
    pdf.cell(100, 6.5, "T.BANGKAEW, A.BANGPLEE SAMUT PRAKARN 10540", ln=True)
    pdf.cell(100, 6.5, "TEL : 662 - 1307822 , EMAIL : sales@rocco-thailand.com", ln=True)
    pdf.ln(5)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)
    
    if has_font: pdf.set_font("THSarabun", "B", 18)
    pdf.set_text_color(28, 69, 135)
    pdf.cell(0, 10, "BOOKING CONFIRMATION", ln=True, align="C")
    pdf.ln(4)
    
    sender_name = safe_str(bk_row.get('Sender'))
    sender_phone = ""
    if sender_name and not df_sender.empty:
        match = df_sender[df_sender['Sender Name'].astype(str) == sender_name]
        if not match.empty: sender_phone = safe_str(match.iloc[0].get('Sender Phone'))
            
    volume_list = []
    if not df_bd.empty and 'Booking ID' in df_bd.columns:
        b_id = safe_str(bk_row.get('Booking ID'))
        containers = df_bd[df_bd['Booking ID'].astype(str) == b_id]
        for _, c_row in containers.iterrows():
            qty = int(safe_float(c_row.get('Number'), 0))
            ctype = safe_str(c_row.get('Container Type'))
            if qty > 0 and ctype: volume_list.append(f"{qty}x{ctype}")
    vol_summary = " + ".join(volume_list) if volume_list else "-"
    
    if has_font: pdf.set_font("THSarabun", "B", 15)
    pdf.set_text_color(200, 60, 60)
    pdf.cell(120, 6, f"BOOKING NUMBER: {safe_str(bk_row.get('Booking Number'))}", border=0)
    if has_font: pdf.set_font("THSarabun", "B", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(70, 6, f"DATE: {format_doc_date(bk_row.get('Booking Date'))}", border=0, align="R", ln=True)
    
    pdf.cell(120, 6, f"CUSTOMER NAME: {safe_str(bk_row.get('Customer'))}", border=0)
    pdf.cell(70, 6, f"CONTACT: {safe_str(bk_row.get('Contact Person'))}", border=0, ln=True)
    pdf.cell(120, 6, f"FROM: {sender_name}", border=0)
    pdf.cell(70, 6, f"TEL: {sender_phone}", border=0, ln=True)
    pdf.ln(4)
    
    if has_font: pdf.set_font("THSarabun", "B", 9)
    pdf.set_draw_color(150, 150, 150)
    line_h = 7
    
    with pdf.table(text_align=("L", "L", "L", "L"), col_widths=(30, 65, 30, 65), line_height=line_h, width=190) as table:
        row = table.row()
        row.cell("LINER")
        row.cell(safe_str(bk_row.get('Liner')), colspan=3)
        row = table.row()
        row.cell("TAX ID")
        row.cell(clean_val(bk_row.get('Liner Tax ID')), colspan=3)
        
        w_val = safe_float(bk_row.get('Weight'))
        m_val = safe_float(bk_row.get('Measurement'))
        wt_str = f"{w_val:,.2f} Kg" if w_val > 0 else "-"
        ms_str = f"{m_val:,.2f}" if m_val > 0 else "-"
        row = table.row()
        row.cell("COMMODITY")
        row.cell(f"{safe_str(bk_row.get('Commodity'))}     |     WEIGHT:  {wt_str}     |     MEASUREMENT:  {ms_str}", colspan=3)
        
        row = table.row()
        row.cell("VOLUME")
        row.cell(vol_summary, colspan=3)
        
        row = table.row()
        row.cell("FEEDER / VOY")
        row.cell(safe_str(bk_row.get('Feeder/Voyage')))
        row.cell("ETD")
        row.cell(format_doc_date(bk_row.get('ETD')))
        row = table.row()
        row.cell("VESSEL / VOY")
        row.cell(safe_str(bk_row.get('Vessel/Voyage')))
        row.cell("ETA")
        row.cell(format_doc_date(bk_row.get('ETA')))
        row = table.row()
        row.cell("LOADING PORT")
        row.cell(safe_str(bk_row.get('Port Loading')))
        row.cell("DISCHARGE PORT")
        row.cell(safe_str(bk_row.get('Port Discharge')))
        row = table.row()
        row.cell("FINAL DESTINATION") 
        row.cell(safe_str(bk_row.get('Final Destination')), colspan=3)
        row = table.row()
        row.cell("CY DATE") 
        row.cell(format_doc_date(bk_row.get('Pick Up Date')))
        row.cell("CY PLACE") 
        row.cell(safe_str(bk_row.get('Pick Up Place')))
        row = table.row()
        row.cell("RETURN DATE")
        row.cell(format_doc_date(bk_row.get('Return Date')))
        row.cell("RETURN PLACE") 
        row.cell(safe_str(bk_row.get('Return Place'))) 
        
        def add_cut_off_row(label, date_val, time_val):
            r = table.row()
            r.cell(label)
            d_str = format_doc_date(date_val)
            t_str = safe_str(time_val)
            combine = f"{d_str}   @   {t_str}" if d_str else "-"
            r.cell(combine, colspan=3)

        add_cut_off_row("CLOSING TIME", bk_row.get('Container Cut Off Date'), bk_row.get('Container Cut Off Time'))
        add_cut_off_row("S/I CUT OFF", bk_row.get('S/I Cut Off Date'), bk_row.get('S/I Cut Off Time'))
        add_cut_off_row("VGM CUT OFF", bk_row.get('VGM Cut Off Date'), bk_row.get('VGM Cut Off Time'))
        add_cut_off_row("B/L CONFIRMED", bk_row.get('B/L Cut Off Date'), bk_row.get('B/L Cut Off Time'))
        
        row = table.row()
        row.cell("FIRST RETURN") 
        row.cell(format_doc_date(bk_row.get('First Return Date')), colspan=3)
        row = table.row()
        row.cell("PAPERLESS CODE")
        row.cell(clean_val(bk_row.get('Paperless Code')), colspan=3)
        row = table.row()
        row.cell("REMARK")
        row.cell(safe_str(bk_row.get('Remark')), colspan=3)

    return bytes(pdf.output())

# -------------------------------------------------------------------------
# 🛠️ ฟังก์ชันหัวกระดาษบริษัทร่วมใช้
def draw_company_header_generic(pdf, has_font, title_text, doc_no, doc_date, is_receipt=False, comp_sz=20, addr_sz=13, title_sz=16, doc_sz=13):
    doc_date = format_doc_date(doc_date)
    if not has_font: pdf.set_font("Arial", size=12)
    try: pdf.image("logo.png", x=150, y=10, w=45)
    except: pass 
        
    if has_font: pdf.set_font("THSarabun", "B", comp_sz)
    pdf.set_text_color(28, 69, 135)
    pdf.cell(100, 8, "ROCCO (THAILAND) CO., LTD.", ln=True)
    
    if has_font: pdf.set_font("THSarabun", "", addr_sz)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(100, 6, "90/123 MOO 15, PLEX-BANGNA, BANGNA-TRAD ROAD,", ln=True)
    pdf.cell(100, 6, "T.BANGKAEW, A.BANGPLEE SAMUT PRAKARN 10540", ln=True)
    pdf.cell(100, 6, "TEL : 662 - 1307822 , EMAIL : sales@rocco-thailand.com", ln=True)
    pdf.cell(100, 6, "TAX ID: 0115560022933 / HEAD OFFICE", ln=True)
    pdf.ln(5)
    
    pdf.set_draw_color(180, 180, 180)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)
    
    if has_font: pdf.set_font("THSarabun", "B", title_sz)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(63, 8, title_text, 0, 0, "L")
    
    pdf.set_text_color(200, 60, 60)
    if has_font: pdf.set_font("THSarabun", "B", doc_sz)
    if is_receipt:
        pdf.cell(64, 8, f"NO: {doc_no}", 0, 0, "C")
        pdf.set_text_color(0, 0, 0)
        pdf.cell(63, 8, f"BOOK NO: 1", 0, 1, "R")
        pdf.cell(190, 8, f"DATE: {doc_date}", 0, 1, "R")
    else:
        pdf.cell(64, 8, f"INVOICE NO: {doc_no}", 0, 0, "C")
        pdf.set_text_color(0, 0, 0)
        pdf.cell(63, 8, f"DATE: {doc_date}", 0, 1, "R")
    pdf.ln(2)

# 🛠️ ฟังก์ชันจัดเรียง Charge Item มาตรฐาน (ใช้เหมือนกันทั้ง Invoice และ Receipt)
def get_item_sort_key(itm):
    charge = str(itm.get('Charge Item', '')).upper()
    ctype = str(itm.get('Container Type', '')).upper()
    sort_order = [
        "OCEAN FREIGHT", "THC", "SEAL FEE", "BL FEE", "AFR", "ENS", "AMS",
        "SURRENDER FEE", "EXPORT CUSTOMS CLEARANCE", "TRUCKING CHARGE",
        "GATE CHARGE", "CFS CHARGE", "C/O", "EDI FEE", "HANDLING FEE"
    ]
    base_idx = 999
    for i, base in enumerate(sort_order):
        if base in charge:
            base_idx = i
            break
    ctype_idx = 999
    if "20" in ctype or "20" in charge: ctype_idx = 1
    elif "40" in ctype or "40" in charge: ctype_idx = 2
    elif "LCL" in ctype or "LCL" in charge: ctype_idx = 3
    return (base_idx, ctype_idx, charge)

# 🛠️ ฟังก์ชันใบแจ้งหนี้ PDF (อัปเดตระบบปัดเศษและ Custom Sort สำหรับ LCL)
def create_invoice_pdf(inv_row, inv_dtl, bk_row, bank_info, cust_address, df_bd, cust_tax):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    try:
        pdf.add_font("THSarabun", style="", fname="THSarabunNew.ttf", uni=True)
        pdf.add_font("THSarabun", style="B", fname="THSarabunNew Bold.ttf", uni=True)
        has_font = True
    except: has_font = False

    # Override set_font dynamically to handle missing fonts gracefully
    original_set_font = pdf.set_font
    def safe_set_font(family, style="", size=0, *args, **kwargs):
        if family == "THSarabun" and not has_font:
            family = "helvetica"
        if family.lower() == "arial":
            family = "helvetica"
        return original_set_font(family, style, size, *args, **kwargs)
    pdf.set_font = safe_set_font
    pdf.set_font("helvetica", "B", 12)

    def draw_company_header():
        inv_date = format_doc_date(inv_row.get('Invoice Date'))
        draw_company_header_generic(pdf, has_font, "INVOICE / ใบแจ้งหนี้", safe_str(inv_row.get('Invoice ID')), inv_date, is_receipt=False, comp_sz=16, addr_sz=10, title_sz=14, doc_sz=14)

    pdf.add_page()
    draw_company_header()
    
    if has_font: pdf.set_font("THSarabun", "", 11)
    pdf.set_x(10)
    pdf.cell(0, 6, f"CUSTOMER: {safe_str(inv_row.get('Customer Name'))}", ln=True)
    if has_font: pdf.set_font("THSarabun", "B", 9)
    pdf.set_x(10)
    pdf.multi_cell(0, 6, f"ADDRESS: {cust_address}")
    pdf.set_x(10)
    pdf.cell(0, 6, f"TAX ID: {cust_tax}", ln=True) 
    pdf.ln(3)

    if has_font: pdf.set_font("THSarabun", "B", 14)
    pdf.cell(0, 8, "SHIPMENT DETAILS", ln=True)
    
    if has_font: pdf.set_font("THSarabun", "B", 9)
    volume_list = []
    if not df_bd.empty and 'Booking ID' in df_bd.columns:
        containers = df_bd[df_bd['Booking ID'].astype(str) == safe_str(bk_row.get('Booking ID'))]
        for _, c_row in containers.iterrows():
            qty = int(safe_float(c_row.get('Number'), 0))
            ctype = safe_str(c_row.get('Container Type'))
            if qty > 0 and ctype: volume_list.append(f"{qty}x{ctype}")
    vol_summary = " + ".join(volume_list) if volume_list else "-"

    pdf.cell(0, 6, f"BOOKING NO: {safe_str(bk_row.get('Booking Number'))}   |   B/L NO: {safe_str(bk_row.get('B/L Number'))}", ln=True)
    pdf.cell(0, 6, f"FEEDER / VOY: {safe_str(bk_row.get('Feeder/Voyage'))}   |   ETD: {format_doc_date(bk_row.get('ETD'))}", ln=True)
    pdf.cell(0, 6, f"VESSEL / VOY: {safe_str(bk_row.get('Vessel/Voyage'))}   |   ETA: {format_doc_date(bk_row.get('ETA'))}", ln=True)
    pdf.cell(0, 6, f"LOADING PORT: {safe_str(bk_row.get('Port Loading'))}   |   DISCHARGE PORT: {safe_str(bk_row.get('Port Discharge'))}", ln=True)
    pdf.cell(0, 6, f"VOLUME: {vol_summary}", ln=True)
    pdf.ln(3)

    service_items = []
    reimb_items = []
    for _, item in inv_dtl.iterrows():
        if safe_float(item.get('Unit Price'), 0) <= 0 and safe_float(item.get('Amount'), 0) <= 0:
            continue
        if safe_bool(item.get('Reimbursement')): reimb_items.append(item.to_dict())
        else: service_items.append(item.to_dict())

    service_items.sort(key=get_item_sort_key)
    reimb_items.sort(key=get_item_sort_key)

    if has_font: pdf.set_font("THSarabun", "B", 9)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(75, 8, "DESCRIPTION", 1, 0, "C", fill=True)
    pdf.cell(15, 8, "QTY", 1, 0, "C", fill=True)
    pdf.cell(25, 8, "UNIT PRICE", 1, 0, "C", fill=True)
    pdf.cell(15, 8, "CUR.", 1, 0, "C", fill=True)
    pdf.cell(25, 8, "EXCHANGE", 1, 0, "C", fill=True)
    pdf.cell(35, 8, "AMOUNT (THB)", 1, 1, "C", fill=True)
    
    if has_font: pdf.set_font("THSarabun", "B", 9)
    for item in service_items:
        ctype_val = safe_str(item.get('Container Type'))
        desc = safe_str(item.get('Charge Item'))
        if ctype_val and ctype_val != "- (Per Shipment)": desc += f" ({ctype_val})"
            
        pdf.cell(75, 8, desc, 1)
        pdf.cell(15, 8, f"{safe_float(item.get('Quantity'), 0):.0f}" if "LCL" not in ctype_val else f"{safe_float(item.get('Quantity'), 0):,.2f}", 1, 0, "C")
        pdf.cell(25, 8, f"{safe_float(item.get('Unit Price'), 0):,.2f}", 1, 0, "R")
        pdf.cell(15, 8, safe_str(item.get('Currency')) or "THB", 1, 0, "C")
        pdf.cell(25, 8, f"{safe_float(item.get('Exchange Rate'), 1):,.4f}", 1, 0, "C")
        pdf.cell(35, 8, f"{safe_float(item.get('Amount'), 0):,.2f}", 1, 1, "R")

    pdf.ln(2)
    s_tot = round_half_up(safe_float(inv_row.get('Total Amount'), 0), 2)
    v_tot = round_half_up(safe_float(inv_row.get('VAT Amount'), 0), 2)
    w_tot = round_half_up(safe_float(inv_row.get('WHT Amount'), 0), 2)
    srv_grand = round_half_up(s_tot + v_tot - w_tot, 2)
    
    vat_label = "VAT"
    for item in service_items:
        v_rate = safe_float(item.get('VAT Rate (%)', 0))
        if v_rate > 0:
            vat_label = f"VAT {v_rate:.0f}%"
            break
    
    if has_font: pdf.set_font("THSarabun", "B", 9)
    summary_text = f"SUBTOTAL: {s_tot:,.2f}   /   {vat_label}: {v_tot:,.2f}   /   WHT: -{w_tot:,.2f}   /   TOTAL: {srv_grand:,.2f}"
    pdf.cell(0, 8, summary_text, 0, 1, "R")
    pdf.ln(3)

    reimb_grand = round_half_up(safe_float(inv_row.get('Reimbursement Amount'), 0), 2)
    net_payment = round_half_up(srv_grand + reimb_grand, 2)

    def draw_footer_and_bank():
        if has_font: pdf.set_font("THSarabun", "B", 10)
        pdf.set_fill_color(220, 235, 255)
        pdf.cell(150, 10, "NET PAYMENT (ยอดชำระสุทธิ) :", 1, 0, "R", fill=True)
        pdf.set_text_color(200, 60, 60)
        pdf.cell(40, 10, f"{net_payment:,.2f} THB", 1, 1, "C", fill=True)
        
        pdf.ln(10)
        pdf.set_text_color(0, 0, 0)
        if has_font: pdf.set_font("THSarabun", "B", 9)
        pdf.cell(0, 6, "BANK DETAILS:", ln=True)
        if has_font: pdf.set_font("THSarabun", "B", 9)
        pdf.cell(0, 6, bank_info, ln=True)
        pdf.cell(0, 6, "Please pay cash/cheque to \" ROCCO (THAILAND) CO., LTD. \"", ln=True)
        pdf.ln(15)
        pdf.cell(95, 6, "Authorized signature ...........................................", 0, 0, "C")
        pdf.cell(95, 6, "Date ...........................................", 0, 1, "C")

    if reimb_items:
        pdf.ln(5)
        if has_font: pdf.set_font("THSarabun", "B", 9)
        pdf.set_text_color(200, 60, 60)
        pdf.cell(0, 6, "*** TO BE CONTINUED ON PAGE 2 ***", ln=True, align="C")
        
        pdf.add_page()
        draw_company_header()

        pdf.set_text_color(0, 0, 0)
        if has_font: pdf.set_font("THSarabun", "B", 15)
        pdf.cell(0, 8, "REIMBURSEMENT (จ่ายแทน)", ln=True)
        
        if has_font: pdf.set_font("THSarabun", "B", 9)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(75, 8, "DESCRIPTION", 1, 0, "C", fill=True)
        pdf.cell(15, 8, "QTY", 1, 0, "C", fill=True)
        pdf.cell(25, 8, "UNIT PRICE", 1, 0, "C", fill=True)
        pdf.cell(15, 8, "CUR.", 1, 0, "C", fill=True)
        pdf.cell(25, 8, "EXCHANGE", 1, 0, "C", fill=True)
        pdf.cell(35, 8, "AMOUNT (THB)", 1, 1, "C", fill=True)
        
        if has_font: pdf.set_font("THSarabun", "B", 9)
        for item in reimb_items:
            ctype_val = safe_str(item.get('Container Type'))
            desc = safe_str(item.get('Charge Item'))
            if ctype_val and ctype_val != "- (Per Shipment)": desc += f" ({ctype_val})"

            pdf.cell(75, 8, desc, 1)
            pdf.cell(15, 8, f"{safe_float(item.get('Quantity'), 0):.0f}" if "LCL" not in ctype_val else f"{safe_float(item.get('Quantity'), 0):,.2f}", 1, 0, "C")
            pdf.cell(25, 8, f"{safe_float(item.get('Unit Price'), 0):,.2f}", 1, 0, "R")
            pdf.cell(15, 8, safe_str(item.get('Currency')) or "THB", 1, 0, "C")
            pdf.cell(25, 8, f"{safe_float(item.get('Exchange Rate'), 1):,.4f}", 1, 0, "C")
            pdf.cell(35, 8, f"{safe_float(item.get('Amount'), 0):,.2f}", 1, 1, "R")
            
        pdf.ln(2)
        if has_font: pdf.set_font("THSarabun", "B", 9)
        pdf.cell(165, 8, "REIMBURSEMENT TOTAL:", 0, 0, "R")
        pdf.cell(25, 8, f"{reimb_grand:,.2f}", 0, 1, "R")
        pdf.ln(5)
        
        draw_footer_and_bank()
    else:
        draw_footer_and_bank()

    return bytes(pdf.output())

def num_to_thai_baht(number):
    """ฟังก์ชันแปลงตัวเลขเป็นคำอ่านภาษาไทย"""
    if number == 0: return "ศูนย์บาทถ้วน"
    txt_num = ["ศูนย์", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
    txt_unit = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน", "ล้าน"]
    
    def process_int(val):
        s = str(val)
        if s == "0": return "ศูนย์"
        res = ""
        length = len(s)
        for i, digit in enumerate(s):
            n = int(digit)
            if n != 0:
                place = length - i - 1
                if place % 6 == 1 and n == 1 and i != 0:
                    res += "สิบ"
                elif place % 6 == 1 and n == 2:
                    res += "ยี่สิบ"
                elif place % 6 == 1:
                    res += txt_num[n] + "สิบ"
                elif place % 6 == 0 and n == 1 and i != 0 and length > 1:
                    res += "เอ็ด"
                else:
                    res += txt_num[n] + txt_unit[place % 6]
                if place > 0 and place % 6 == 0:
                    res += "ล้าน"
        return res
        
    num_str = f"{number:.2f}"
    parts = num_str.split('.')
    baht = int(parts[0])
    satang = int(parts[1])
    
    text = process_int(baht) + "บาท" if baht > 0 else ""
    if satang > 0:
        text += process_int(satang) + "สตางค์"
    else:
        text += "ถ้วน"
    return text

def create_receipt_pdf(rec_row, inv_row, inv_dtl, bk_row, is_copy=False):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    try:
        pdf.add_font("THSarabun", style="", fname="THSarabunNew.ttf", uni=True)
        pdf.add_font("THSarabun", style="B", fname="THSarabunNew Bold.ttf", uni=True)
        has_font = True
    except: has_font = False

    # Override set_font dynamically to handle missing fonts gracefully
    original_set_font = pdf.set_font
    def safe_set_font(family, style="", size=0, *args, **kwargs):
        if family == "THSarabun" and not has_font:
            family = "helvetica"
        if family.lower() == "arial":
            family = "helvetica"
        return original_set_font(family, style, size, *args, **kwargs)
    pdf.set_font = safe_set_font
    pdf.set_font("helvetica", "B", 12)

    pdf.add_page()
    
    # ---------------- HEADER ----------------
    # ---------------- HEADER ----------------
    if has_font: pdf.set_font("THSarabun", "B", 16)
    pdf.cell(0, 8, "บริษัท ร็อคโก้ (ประเทศไทย) จำกัด", ln=True, align="C")
    pdf.set_font("THSarabun", "B", 12)
    pdf.cell(0, 8, "ROCCO (THAILAND) CO., LTD.", ln=True, align="C")
    
    if has_font: pdf.set_font("THSarabun", "B", 9)
    pdf.cell(0, 5, "สำนักงานใหญ่ : 90/123 หมู่ 15 เพล็กซ์-บางนา ถนน บางนา-ตราด ตำบล บางแก้ว อำเภอ บางพลี จังหวัด สมุทรปราการ 10540", ln=True, align="C")
    pdf.cell(0, 5, "Head Office : 90/123 MOO 15, PLEX-BANGNA, BANGNA-TRAD ROAD, T.BANGKAEW, A.BANGPLEE SAMUT PRAKARN 10540", ln=True, align="C")
    pdf.cell(0, 5, "Tel : 662 - 1307822   Fax : 662 - 1307823", ln=True, align="C")
    pdf.cell(0, 5, "เลขประจำตัวผู้เสียภาษี 0 1 1 5 5 6 0 0 2 2 9 3 3", ln=True, align="C")
    pdf.ln(5)
    
    # ---------------- DOC NO & TITLE ----------------
    rec_id = safe_str(rec_row.get('Receipt ID'))
    
    title_th = "สำเนาใบเสร็จรับเงิน / สำเนาใบกำกับภาษี" if is_copy else "ใบเสร็จรับเงิน / ใบกำกับภาษี"
    title_en = "Copy Receipt / Copy Tax Invoice" if is_copy else "Receipt / Tax Invoice"
    
    if has_font: pdf.set_font("THSarabun", "", 11)
    pdf.cell(15, 8, "เล่มที่", 0, 0, "L")
    pdf.cell(30, 8, "1", 'B', 0, "C")
    
    if has_font: pdf.set_font("THSarabun", "B", 14)
    pdf.cell(100, 8, title_th, 0, 0, "C")
    
    if has_font: pdf.set_font("THSarabun", "", 11)
    pdf.cell(15, 8, "เลขที่", 0, 0, "R")
    pdf.cell(30, 8, rec_id, 'B', 1, "C")
    
    if has_font: pdf.set_font("THSarabun", "B", 10)
    pdf.cell(190, 6, title_en, 0, 1, "C")
    pdf.ln(3)

    # ---------------- CUSTOMER DETAILS ----------------
    c_name = safe_str(rec_row.get('Customer Name'))
    c_addr = safe_str(rec_row.get('Customer Address')).replace('\n', ' ')
    c_tax = safe_str(rec_row.get('Customer Tax ID'))
    
    df_cust = get_data_from_sheet('Customer')
    if not df_cust.empty and c_name:
        match_c = df_cust[df_cust['Customer Name'].astype(str) == c_name]
        if not match_c.empty:
            c_addr = safe_str(match_c.iloc[0].get('Address', c_addr)).replace('\n', ' ')
            c_tax = safe_str(match_c.iloc[0].get('Tax ID', c_tax))

    r_date = format_doc_date(rec_row.get('Receipt Date'))
    bl_no = safe_str(bk_row.get('B/L Number')) if bk_row is not None else ""
    vessel = safe_str(bk_row.get('Feeder/Voyage')) if bk_row is not None else ""
    
    if has_font: pdf.set_font("THSarabun", "B", 11)
    
    pdf.cell(20, 6, "ชื่อผู้ซื้อ", 0, 0, "L")
    pdf.set_font("THSarabun", "", 11)
    pdf.cell(130, 6, c_name, 0, 0, "L")
    pdf.set_font("THSarabun", "B", 11)
    pdf.cell(15, 6, "วันที่", 0, 0, "R")
    pdf.set_font("THSarabun", "", 11)
    pdf.cell(25, 6, r_date, 0, 1, "R")
    
    pdf.set_font("THSarabun", "B", 11)
    pdf.cell(20, 6, "ที่อยู่", 0, 0, "L")
    pdf.set_font("THSarabun", "", 11)
    
    current_y = pdf.get_y()
    pdf.set_left_margin(30)
    pdf.set_y(current_y)
    pdf.multi_cell(0, 6, c_addr, 0, "L")
    
    pdf.set_left_margin(10)
    pdf.set_x(10)
    
    pdf.set_font("THSarabun", "B", 11)
    pdf.cell(40, 6, "เลขประจำตัวผู้เสียภาษี", 0, 0, "L")
    pdf.set_font("THSarabun", "", 11)
    pdf.cell(150, 6, c_tax, 0, 1, "L")

    pdf.set_font("THSarabun", "B", 11)
    pdf.cell(20, 6, "B/L No.", 0, 0, "L")
    pdf.set_font("THSarabun", "", 11)
    pdf.cell(80, 6, bl_no, 0, 1, "L")
    
    pdf.set_font("THSarabun", "B", 11)
    pdf.cell(20, 6, "ชื่อเรือ", 0, 0, "L")
    pdf.set_font("THSarabun", "", 11)
    pdf.cell(80, 6, vessel, 0, 1, "L")
    pdf.ln(5)

    # ---------------- ITEMS TABLE ----------------
    if has_font: pdf.set_font("THSarabun", "B", 11)
    pdf.cell(15, 8, "ลำดับที่", 1, 0, "C")
    pdf.cell(135, 8, "รายละเอียดของสินค้าหรือบริการ", 1, 0, "C")
    pdf.cell(40, 8, "จำนวนเงิน (ไม่รวมภาษี)", 1, 1, "C")
    
    if has_font: pdf.set_font("THSarabun", "", 11)
    
    service_items = []
    reimb_items = []
    if not inv_dtl.empty:
        for _, item in inv_dtl.iterrows():
            if safe_float(item.get('Unit Price'), 0) <= 0 and safe_float(item.get('Amount'), 0) <= 0:
                continue
            if safe_bool(item.get('Reimbursement')): reimb_items.append(item.to_dict())
            else: service_items.append(item.to_dict())

    service_items.sort(key=get_item_sort_key)
    reimb_items.sort(key=get_item_sort_key)

    counter = 1
    total_base_amt = 0.0
    for item in service_items:
        desc = safe_str(item.get('Charge Item'))
        ctype_val = safe_str(item.get('Container Type'))
        if ctype_val and ctype_val != "- (Per Shipment)":
            desc += f" ({ctype_val})"
            
        amt = safe_float(item.get('Amount'), 0)
        total_base_amt += amt
        pdf.cell(15, 6, str(counter), 'LR', 0, "C")
        pdf.cell(135, 6, desc, 'LR', 0, "L")
        pdf.cell(40, 6, f"{amt:,.2f}", 'LR', 1, "R")
        counter += 1



    current_y = pdf.get_y()
    if current_y < 170:
        pdf.cell(15, 170 - current_y, "", 'LR', 0)
        pdf.cell(135, 170 - current_y, "", 'LR', 0)
        pdf.cell(40, 170 - current_y, "", 'LR', 1)
        
    pdf.cell(190, 0, "", 'T', 1)

    # ---------------- SUMMARY ----------------
    s_tot = round_half_up(safe_float(inv_row.get('Total Amount'), 0), 2)
    v_tot = round_half_up(safe_float(inv_row.get('VAT Amount'), 0), 2)
    
    vat_rate_show = 0.0
    if not inv_dtl.empty:
        for _, item in inv_dtl.iterrows():
            v = safe_float(item.get('VAT Rate (%)', 0))
            if v > 0:
                vat_rate_show = v
                break
            
    vat_rate_text = f"อัตราภาษี ร้อยละ {vat_rate_show:g}   |   " if v_tot > 0 else ""
    subtotal = s_tot
    grand_total = round_half_up(subtotal + v_tot, 2)

    if has_font: pdf.set_font("THSarabun", "B", 11)
    pdf.cell(150, 6, "รวมราคาทั้งสิ้น", 1, 0, "R")
    pdf.set_font("THSarabun", "", 11)
    pdf.cell(40, 6, f"{subtotal:,.2f}", 1, 1, "R")
    
    if has_font: pdf.set_font("THSarabun", "B", 11)
    pdf.cell(150, 6, f"{vat_rate_text}จำนวนภาษีมูลค่าเพิ่ม", 1, 0, "R")
    pdf.set_font("THSarabun", "", 11)
    pdf.cell(40, 6, f"{v_tot:,.2f}", 1, 1, "R")

    if has_font: pdf.set_font("THSarabun", "B", 11)
    pdf.cell(150, 6, "จำนวนเงินรวมทั้งสิ้น", 1, 0, "R")
    pdf.set_font("THSarabun", "", 11)
    pdf.cell(40, 6, f"{grand_total:,.2f}", 1, 1, "R")

    # ---------------- AMOUNT IN WORDS ----------------
    thai_word = num_to_thai_baht(grand_total)
    pdf.ln(4)
    if has_font: pdf.set_font("THSarabun", "B", 11)
    pdf.cell(40, 8, "จำนวนเงิน (ตัวอักษร)", 0, 0, "L")
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(150, 8, f"-- {thai_word} --", 0, 1, "C", fill=True)
    pdf.ln(5)

    # ---------------- PAYMENT INFO ----------------
    pm_method = safe_str(rec_row.get('Payment Method'))
    pm_ref = safe_str(rec_row.get('Payment Ref'))
    is_cash = 'เงินสด' in pm_method or 'Cash' in pm_method
    pm_show_no = "CASH" if is_cash else pm_ref
    
    if has_font: pdf.set_font("THSarabun", "B", 11)
    pdf.cell(25, 6, "เงินสด/เช็ค", 0, 0, "L")
    pdf.cell(60, 6, "อ้างอิงธนาคาร/เลขที่เช็ค", 0, 0, "R")
    if has_font:
        f_sz = 10  # ลดลง 1 pt ตามที่ขอ (จาก 11 pt เหลือ 10 pt)
        pdf.set_font("THSarabun", "", f_sz)
        while f_sz > 7 and pdf.get_string_width(pm_show_no) > 98:
            f_sz -= 0.5
            pdf.set_font("THSarabun", "", f_sz)
    pdf.cell(5, 6, "", 0, 0)
    pdf.cell(100, 6, pm_show_no, 'B', 1, "L")

    pdf.set_font("THSarabun", "", 9)
    pdf.cell(25, 4, "Cash/Cheque", 0, 0, "L")
    pdf.cell(60, 4, "(Bank / Ref No.)", 0, 0, "R")
    pdf.cell(105, 4, "", 0, 1, "C")
    pdf.ln(12)

    # ---------------- SIGNATURES ----------------
    pdf.set_font("THSarabun", "", 11)
    pdf.cell(95, 6, ".........................................................................", 0, 0, "C")
    pdf.cell(95, 6, ".........................................................................", 0, 1, "C")
    pdf.cell(95, 6, "ผู้รับเงิน", 0, 0, "C")
    pdf.cell(95, 6, "ผู้รับมอบอำนาจ", 0, 1, "C")
    
    pdf.set_font("THSarabun", "", 9)
    pdf.cell(95, 4, "Collector", 0, 0, "C")
    pdf.cell(95, 4, "Authorized Signature", 0, 1, "C")
    
    pdf.ln(8)
    pdf.set_font("THSarabun", "B", 11)
    pdf.cell(0, 5, "กรณีชำระเงินด้วยเช็ค ใบเสร็จรับเงินฉบับนี้ จะสมบูรณ์ต่อเมื่อเช็คได้รับการชำระเงินแล้วเท่านั้น", 0, 1, "C")
    pdf.set_font("THSarabun", "", 9)
    pdf.cell(0, 5, "If payment is made by cheque, this receipt will be valid when the cheque is honoured by the bank.", 0, 1, "C")

    return bytes(pdf.output())

# -------------------------------------------------------------------------
# --- 📌 GLOBAL DATA LOADER ---
df_bk_all_global = get_data_from_sheet('Booking_Header')
bk_opts_costing_global = []
if not df_bk_all_global.empty:
    bk_opts_costing_global = df_bk_all_global.apply(lambda r: f"{r['Booking ID']} - {r.get('Booking Number', '-')} - {r.get('Customer', '-')}", axis=1).tolist()

# --- 📌 SIDEBAR NAVIGATION ---
st.sidebar.title("🚢 ROCCO MINI ERP")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "📌 เมนูหลัก (Main Navigation)",
    [
        "⚙️ ฐานข้อมูลหลัก (Master Data)",
        "🚢 จัดการ Booking & ต้นทุน",
        "🧾 ใบแจ้งหนี้ (Invoice)",
        "💰 รับชำระเงิน (Receipt)",
        "📊 รายงาน (Reports)"
    ]
)
st.sidebar.markdown("---")
st.sidebar.caption("💡 ระบบจัดการข้อมูลการขนส่ง (Supabase Cloud Edition)")

# --- Page 1: ฐานข้อมูลหลัก (Master Data - Option 2 Dropdown) ---
if page == "⚙️ ฐานข้อมูลหลัก (Master Data)":
    st.header("⚙️ จัดการฐานข้อมูลหลัก (Master Data Management)")
    
    master_options = [
        "📋 ข้อมูลลูกค้า (Customer)",
        "🚢 สายเรือ (Liner)",
        "⚓ ท่าเรือต้นทาง (Port Loading)",
        "🏁 ท่าเรือปลายทาง (Port Discharge)",
        "📦 ชนิดตู้คอนเทนเนอร์ (Container Type)",
        "💲 รายการค่าบริการ (Charge Item)",
        "📉 อัตราภาษีหัก ณ ที่จ่าย (Tax %)",
        "📊 อัตราภาษีมูลค่าเพิ่ม (VAT %)",
        "💱 สกุลเงิน (Currency)",
        "👤 ผู้ส่งออก (Sender)"
    ]
    
    sel_master = st.selectbox("📌 เลือกหมวดหมู่ข้อมูลหลักที่ต้องการจัดการ:", master_options)
    st.markdown("---")
    
    if sel_master == "📋 ข้อมูลลูกค้า (Customer)":
        st.subheader("📋 ระบบข้อมูลลูกค้า (Customer Management)")
        cust_tab1, cust_tab2 = st.tabs(["➕ เพิ่มลูกค้าใหม่", "🔍 ค้นหาและแก้ไขลูกค้า"])
        with cust_tab1:
            with st.form("add_cust", clear_on_submit=True):
                st.info("ระบบจะสร้าง Customer ID ให้อัตโนมัติเมื่อกดบันทึก")
                name = st.text_input("Name (ชื่อเต็ม)")
                short_name = st.text_input("Short Name (ชื่อย่อ - สำหรับออกรายงาน)") 
                tel = st.text_input("Tel")
                email = st.text_input("Email")
                addr = st.text_area("Address")
                tax = st.text_input("Tax ID")
                if st.form_submit_button("💾 บันทึกข้อมูลลูกค้า"):
                    if not name:
                        st.error("กรุณาระบุชื่อลูกค้า")
                    else:
                        new_id = generate_next_id('Customer', 'Customer ID', 'C')
                        record = {
                            "Customer ID": new_id, "Customer Name": name, "Customer Short Name": short_name,
                            "Telephone": tel, "Email": email, "Address": addr, "Tax ID": tax
                        }
                        append_record('Customer', record)
                        st.success(f"บันทึกสำเร็จ! รหัสลูกค้าคือ {new_id}")
                        st.rerun()
        with cust_tab2:
            val = st.text_input("🔍 ค้นหาลูกค้าจากชื่อ (พิมพ์ชื่อหรือส่วนหนึ่งของชื่อ)")
            if val:
                df = get_data_from_sheet('Customer')
                if not df.empty and 'Customer Name' in df.columns:
                    res = df[df['Customer Name'].astype(str).str.contains(val, case=False, na=False)]
                    if not res.empty:
                        sel = st.selectbox("เลือกลูกค้า:", res['Customer Name'].tolist())
                        data = res[res['Customer Name'] == sel].iloc[0]
                        rec_id = data['airtable_record_id']
                        with st.form(f"edit_cust_{rec_id}"):
                            n = st.text_input("Name (ชื่อเต็ม)", value=safe_str(data.get('Customer Name')))
                            sn = st.text_input("Short Name (ชื่อย่อ)", value=safe_str(data.get('Customer Short Name'))) 
                            t = st.text_input("Tel", value=safe_str(data.get('Telephone')))
                            e = st.text_input("Email", value=safe_str(data.get('Email')))
                            a = st.text_area("Address", value=safe_str(data.get('Address')))
                            x = st.text_input("Tax ID", value=safe_str(data.get('Tax ID')))
                            if st.form_submit_button("💾 บันทึกการแก้ไข"):
                                record = {"Customer Name": n, "Customer Short Name": sn, "Telephone": t, "Email": e, "Address": a, "Tax ID": x}
                                update_record('Customer', data['airtable_record_id'], record)
                                st.success("แก้ไขเรียบร้อย!")
                                st.rerun()
                    else:
                        st.warning("ไม่พบลูกค้าที่ค้นหา")
    else:
        idx_map = {
            "🚢 สายเรือ (Liner)": 0,
            "⚓ ท่าเรือต้นทาง (Port Loading)": 1,
            "🏁 ท่าเรือปลายทาง (Port Discharge)": 2,
            "📦 ชนิดตู้คอนเทนเนอร์ (Container Type)": 3,
            "💲 รายการค่าบริการ (Charge Item)": 4,
            "📉 อัตราภาษีหัก ณ ที่จ่าย (Tax %)": 5,
            "📊 อัตราภาษีมูลค่าเพิ่ม (VAT %)": 6,
            "💱 สกุลเงิน (Currency)": 7,
            "👤 ผู้ส่งออก (Sender)": 8
        }
        m_idx = idx_map.get(sel_master, 0)
        m = master_configs[m_idx]
        
        st.subheader(f"⚙️ จัดการข้อมูล: {m['name']}")
        s1, s2 = st.tabs([f"➕ เพิ่ม {m['name']}", f"🔍 ค้นหา/แก้ไข {m['name']}"]) 
        with s1:
            with st.form(f"add_{m['sheet']}", clear_on_submit=True):
                st.info("ระบบจะสร้าง ID ให้อัตโนมัติเมื่อกดบันทึก")
                inputs = {col: st.text_input(col, key=f"a_{m['sheet']}_{col}") for col in m['cols']}
                if st.form_submit_button(f"💾 บันทึก {m['name']}"):
                    new_id = generate_next_id(m['sheet'], m['id'], m['pre'])
                    record = {m['id']: new_id}
                    for col in m['cols']: record[col] = inputs[col]
                    append_record(m['sheet'], record)
                    st.success(f"บันทึกสำเร็จ! รหัสคือ {new_id}")
                    st.rerun()
        with s2:
            search_val = st.text_input(f"🔍 ค้นหาจาก {m['cols'][0]}", key=f"s_{m['sheet']}")
            if search_val:
                df = get_data_from_sheet(m['sheet'])
                if not df.empty and m['cols'][0] in df.columns:
                    res = df[df[m['cols'][0]].astype(str).str.contains(search_val, case=False, na=False)]
                    if not res.empty:
                        sel = st.selectbox("เลือกรายการ:", res[m['cols'][0]].tolist(), key=f"sel_{m['sheet']}")
                        d = res[res[m['cols'][0]] == sel].iloc[0]
                        rec_id = d['airtable_record_id']
                        with st.form(f"edit_{m['sheet']}_{rec_id}"):
                            n_vals = {col: st.text_input(col, value=safe_str(d.get(col)), key=f"e_{m['sheet']}_{col}_{rec_id}") for col in m['cols']}
                            if st.form_submit_button("💾 บันทึกการแก้ไข"):
                                update_record(m['sheet'], d['airtable_record_id'], n_vals)
                                st.success("แก้ไขเรียบร้อย!")
                                st.rerun()
                    else:
                        st.warning(f"ไม่พบข้อมูล {m['name']}")

# --- Page 2: จัดการ Booking & Job Costing ---
elif page == "🚢 จัดการ Booking & ต้นทุน":
    st.header("จัดการ Booking Confirmation")
    df_cust = get_data_from_sheet('Customer')
    df_liner = get_data_from_sheet('Liner')
    df_pl = get_data_from_sheet('Port_Loading')
    df_pd = get_data_from_sheet('Port_Discharge')
    df_ct = get_data_from_sheet('Container_Type')
    df_sender = get_data_from_sheet('Sender')
    df_curr = get_data_from_sheet('Currency')

    cust_opts = [safe_str(x) for x in df_cust['Customer Name'].dropna().tolist()] if not df_cust.empty else []
    sender_opts = [safe_str(x) for x in df_sender['Sender Name'].dropna().tolist()] if not df_sender.empty else []
    curr_opts = [safe_str(x) for x in df_curr['Currency'].dropna().tolist()] if not df_curr.empty and 'Currency' in df_curr.columns else ['THB', 'USD']
    if 'THB' not in curr_opts: curr_opts.insert(0, 'THB')
    if 'USD' not in curr_opts: curr_opts.append('USD')
    pl_opts = [safe_str(x) for x in df_pl['Port Name'].dropna().tolist()] if not df_pl.empty else []
    pd_opts = [safe_str(x) for x in df_pd['Port Name'].dropna().tolist()] if not df_pd.empty else []
    liner_opts = [safe_str(x) for x in df_liner['Liner Name'].dropna().tolist()] if not df_liner.empty else []
    
    # df_bk_all_global และ bk_opts_costing_global ถูกโหลดไว้ตั้งแต่ระดับบนสุด (Global) เรียบร้อยแล้ว

    sub_bk1, sub_bk2, sub_bk3 = st.tabs(["➕ สร้าง Booking ใหม่", "🔍 ค้นหาและแก้ไข Booking", "💰 คำนวณต้นทุน-กำไร (Job Costing)"])

    # --- ย่อย 1: สร้าง Booking ---
    with sub_bk1:
        if 'reset_key' not in st.session_state: st.session_state['reset_key'] = 0
        rk = st.session_state['reset_key'] 
        
        # แสดงปุ่มดาวน์โหลด PDF ของ Booking ที่เพิ่งบันทึกสำเร็จล่าสุด
        if 'last_created_bk' in st.session_state and st.session_state['last_created_bk'] is not None:
            last_bk = st.session_state['last_created_bk']
            col_suc_1, col_suc_2 = st.columns([3, 1])
            with col_suc_1:
                st.success(f"🎉 บันทึก Booking ID: {last_bk['id']} (เลขที่: {last_bk['no']}) สำเร็จเรียบร้อยแล้ว!")
            with col_suc_2:
                st.download_button(
                    label="📄 ดาวน์โหลด Confirmation PDF",
                    data=last_bk['pdf'],
                    file_name=f"{last_bk['no'] or last_bk['id']}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="download_last_created_bk"
                )
                if st.button("❌ ปิดการแจ้งเตือน", use_container_width=True, key="clear_last_created_bk"):
                    st.session_state['last_created_bk'] = None
                    st.rerun()
            st.divider()

        st.markdown("#### 1. ข้อมูลทั่วไป (General Info)")
        r1_1, r1_2, r1_3 = st.columns([1, 2, 1])
        with r1_1: bk_date = st.date_input("Booking Date", value=None, format="DD/MM/YYYY", key=f"bk_date_{rk}")
        with r1_2: cust = st.selectbox("Customer", cust_opts, index=None, placeholder="-- เลือกลูกค้า --", key=f"bk_cust_{rk}")
        with r1_3: contact = st.text_input("Contact Person", key=f"bk_contact_{rk}")

        r2_1, r2_2, r2_3 = st.columns([2, 1, 1])
        with r2_1: commodity = st.text_input("Commodity", key=f"bk_commodity_{rk}")
        with r2_2: weight = st.number_input("Weight (Kg)", format="%.2f", value=None, key=f"bk_weight_{rk}")
        with r2_3: measurement = st.number_input("Measurement (CBM)", format="%.2f", value=None, key=f"bk_measurement_{rk}")

        r3_1, r3_2 = st.columns([1, 1])
        with r3_1: bk_no = st.text_input("Booking Number", key=f"bk_no_{rk}")
        with r3_2: bl_no = st.text_input("B/L Number", key=f"bk_bl_no_{rk}")

        r4_1, r4_2 = st.columns([1, 1])
        with r4_1: sender = st.selectbox("Sender", sender_opts, index=None, placeholder="-- เลือกผู้ส่ง --", key=f"bk_sender_{rk}")
        with r4_2:
            sender_phone = ""
            if sender and not df_sender.empty:
                match = df_sender[df_sender['Sender Name'].astype(str) == sender]
                if not match.empty: sender_phone = safe_str(match.iloc[0].get('Sender Phone'))
            st.text_input("Sender Phone", value=sender_phone, disabled=True, key=f"show_s_phone_{rk}")

        st.divider()
        st.markdown("#### 2. รายการบรรจุสินค้า (Containers / LCL)")
        if 'containers' not in st.session_state: st.session_state['containers'] = []
            
        ct_1, ct_2, ct_3 = st.columns([2, 2, 1])
        with ct_1:
            ct_opts = [safe_str(x) for x in df_ct['Container Type'].dropna().tolist()] if not df_ct.empty else []
            sel_ct = st.selectbox("Type", ct_opts, index=None, key=f"bk_sel_ct_{rk}")
        with ct_2: qty = st.number_input("QTY (จำนวนตู้ หรือระบุ 1 สำหรับ LCL)", min_value=1, step=1, value=None, key=f"bk_qty_{rk}")
        with ct_3:
            st.write("") 
            if st.button("➕ เพิ่มรายการตู้/LCL", use_container_width=True, key=f"btn_add_{rk}"):
                if sel_ct and qty:
                    st.session_state['containers'].append({"Container Type": sel_ct, "Number": qty})
                    st.rerun()

        if st.session_state['containers']:
            st.table(st.session_state['containers'])
            if st.button("❌ ล้างรายการบรรจุ", key=f"btn_clear_{rk}"):
                st.session_state['containers'] = []
                st.rerun()

        st.divider()
        st.markdown("#### 3. เส้นทางและเรือ (Routing & Vessel)")
        rv1_1, rv1_2 = st.columns([3, 1])
        with rv1_1: 

            pl = st.selectbox("Port Loading", pl_opts, index=None, key=f"bk_pl_{rk}")
        with rv1_2:
            paperless = ""
            if pl and not df_pl.empty:
                match = df_pl[df_pl['Port Name'].astype(str) == pl]
                if not match.empty: paperless = safe_str(match.iloc[0].get('Paperless Code'))
            st.text_input("Paperless Code", value=paperless, disabled=True, key=f"show_paperless_{rk}")

        rv2_1, rv2_2 = st.columns([1, 1])
        with rv2_1: 

            pd_val = st.selectbox("Port Discharge", pd_opts, index=None, key=f"bk_pd_{rk}")
        with rv2_2: final_dest = st.text_input("Final Destination", key=f"bk_final_dest_{rk}")

        rv3_1, rv3_2 = st.columns([3, 1])
        with rv3_1:

            liner = st.selectbox("Liner", liner_opts, index=None, key=f"bk_liner_{rk}")
        with rv3_2:
            liner_tax = ""
            if liner and not df_liner.empty:
                match = df_liner[df_liner['Liner Name'].astype(str) == liner]
                if not match.empty: liner_tax = safe_str(match.iloc[0].get('Liner Tax ID'))
            st.text_input("Liner Tax ID", value=liner_tax, disabled=True, key=f"show_liner_tax_{rk}")

        rv4_1, rv4_2 = st.columns([3, 1])
        with rv4_1: feeder = st.text_input("Feeder / Voyage", key=f"bk_feeder_{rk}")
        with rv4_2: etd = st.date_input("ETD", value=None, format="DD/MM/YYYY", key=f"bk_etd_{rk}")

        rv5_1, rv5_2 = st.columns([3, 1])
        with rv5_1: vessel = st.text_input("Vessel / Voyage", key=f"bk_vessel_{rk}")
        with rv5_2: eta = st.date_input("ETA", value=None, format="DD/MM/YYYY", key=f"bk_eta_{rk}")

        st.divider()
        st.markdown("#### 4. วันเวลา Cut Off และสถานที่")
        co1_1, co1_2 = st.columns([1, 3])
        with co1_1: pickup_date = st.date_input("Pick Up Date", value=None, format="DD/MM/YYYY", key=f"bk_pickup_date_{rk}")
        with co1_2: pickup_place = st.text_input("Pick Up Place", key=f"bk_pickup_place_{rk}")

        co2_1, co2_2 = st.columns([1, 3])
        with co2_1: return_date = st.date_input("Return Date", value=None, format="DD/MM/YYYY", key=f"bk_return_date_{rk}")
        with co2_2: return_place = st.text_input("Return Place", key=f"bk_return_place_{rk}")

        co3_1, co3_2 = st.columns([1, 1])
        with co3_1: cy_date = st.date_input("Container Cut Off Date", value=None, format="DD/MM/YYYY", key=f"bk_cy_date_{rk}")
        with co3_2: cy_time = st.time_input("Container Cut Off Time", value=None, key=f"bk_cy_time_{rk}")

        co4_1, co4_2 = st.columns([1, 1])
        with co4_1: si_date = st.date_input("S/I Cut Off Date", value=None, format="DD/MM/YYYY", key=f"bk_si_date_{rk}")
        with co4_2: si_time = st.time_input("S/I Cut Off Time", value=None, key=f"bk_si_time_{rk}")

        co5_1, co5_2 = st.columns([1, 1])
        with co5_1: vgm_date = st.date_input("VGM Cut Off Date", value=None, format="DD/MM/YYYY", key=f"bk_vgm_date_{rk}")
        with co5_2: vgm_time = st.time_input("VGM Cut Off Time", value=None, key=f"bk_vgm_time_{rk}")

        co6_1, co6_2 = st.columns([1, 1])
        with co6_1: bl_date = st.date_input("B/L Cut Off Date", value=None, format="DD/MM/YYYY", key=f"bk_bl_date_{rk}")
        with co6_2: bl_time = st.time_input("B/L Cut Off Time", value=None, key=f"bk_bl_time_{rk}")

        co7_1, co7_2 = st.columns([1, 1])
        with co7_1: first_return = st.date_input("First Return Date", value=None, format="DD/MM/YYYY", key=f"bk_first_return_{rk}")

        remark = st.text_area("Remark", key=f"bk_remark_{rk}")
        
        st.divider()
        col_btn_1, col_btn_2 = st.columns([1, 1])
        
        with col_btn_1:
            btn_save = st.button("💾 ยืนยันการบันทึก Booking", type="primary", use_container_width=True, key=f"btn_save_{rk}")
            
        with col_btn_2:
            # สร้างตัวแปรจำลองข้อมูลปัจจุบันในฟอร์มเพื่อออก PDF
            preview_bk_row = {
                "Booking ID": "PREVIEW",
                "Booking Date": fmt_date(bk_date),
                "Booking Number": safe_str(bk_no),
                "B/L Number": safe_str(bl_no),
                "Customer": cust,
                "Contact Person": contact,
                "Commodity": commodity,
                "Weight": weight,
                "Measurement": measurement,
                "Liner": liner,
                "Liner Tax ID": liner_tax,
                "Port Loading": pl,
                "Paperless Code": paperless,
                "Port Discharge": pd_val,
                "Final Destination": final_dest,
                "Feeder/Voyage": feeder,
                "ETD": fmt_date(etd),
                "Vessel/Voyage": vessel,
                "ETA": fmt_date(eta),
                "Pick Up Date": fmt_date(pickup_date),
                "Pick Up Place": pickup_place,
                "Return Date": fmt_date(return_date),
                "Return Place": return_place,
                "Container Cut Off Date": fmt_date(cy_date),
                "Container Cut Off Time": fmt_time(cy_time),
                "VGM Cut Off Date": fmt_date(vgm_date),
                "VGM Cut Off Time": fmt_time(vgm_time),
                "S/I Cut Off Date": fmt_date(si_date),
                "S/I Cut Off Time": fmt_time(si_time),
                "B/L Cut Off Date": fmt_date(bl_date),
                "B/L Cut Off Time": fmt_time(bl_time),
                "First Return Date": fmt_date(first_return),
                "Remark": remark,
                "Sender": sender
            }
            
            preview_df_bd = pd.DataFrame(st.session_state.get('containers', []))
            if not preview_df_bd.empty:
                preview_df_bd['Booking ID'] = 'PREVIEW'
                
            preview_pdf_bytes = create_booking_confirmation_pdf(preview_bk_row, preview_df_bd, df_sender)
            
            st.download_button(
                label="📄 ดาวน์โหลด Booking Confirmation PDF (ดราฟต์)",
                data=preview_pdf_bytes,
                file_name=f"{bk_no or 'Draft'}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"btn_preview_pdf_{rk}"
            )
            
        if btn_save:
            if not st.session_state['containers']:
                st.error("กรุณาเพิ่มรายการตู้คอนเทนเนอร์/LCL อย่างน้อย 1 รายการก่อนบันทึกครับ")
            else:
                with st.spinner("กำลังบันทึกข้อมูล..."):
                    try:
                        new_bk_id = generate_next_id('Booking_Header', 'Booking ID', 'BK')
                        header_record = {
                            "Booking ID": new_bk_id, "Booking Date": fmt_date(bk_date),
                            "Booking Number": safe_str(bk_no), "B/L Number": safe_str(bl_no),
                            "Customer": cust, "Contact Person": contact, "Commodity": commodity,
                            "Weight": weight, "Measurement": measurement, "Liner": liner,
                            "Liner Tax ID": liner_tax, "Port Loading": pl, "Paperless Code": paperless,
                            "Port Discharge": pd_val, "Final Destination": final_dest, "Feeder/Voyage": feeder,
                            "ETD": fmt_date(etd), "Vessel/Voyage": vessel, "ETA": fmt_date(eta),
                            "Pick Up Date": fmt_date(pickup_date), "Pick Up Place": pickup_place,
                            "Return Date": fmt_date(return_date), "Return Place": return_place,
                            "Container Cut Off Date": fmt_date(cy_date), "Container Cut Off Time": fmt_time(cy_time),
                            "VGM Cut Off Date": fmt_date(vgm_date), "VGM Cut Off Time": fmt_time(vgm_time),
                            "S/I Cut Off Date": fmt_date(si_date), "S/I Cut Off Time": fmt_time(si_time),
                            "B/L Cut Off Date": fmt_date(bl_date), "B/L Cut Off Time": fmt_time(bl_time),
                            "First Return Date": fmt_date(first_return), "Remark": remark, "Sender": sender
                        }
                        append_record('Booking_Header', header_record)
                        
                        max_bd_num = 0
                        df_bd = get_data_from_sheet('Booking_Detail')
                        if not df_bd.empty and 'Detail ID' in df_bd.columns:
                            for val in df_bd['Detail ID'].dropna():
                                v_str = safe_str(val)
                                if v_str.startswith('BD'):
                                    try:
                                        num = int(v_str.replace('BD', ''))
                                        if num > max_bd_num: max_bd_num = num
                                    except: pass
                                    
                        rows_to_append = []
                        for idx, item in enumerate(st.session_state['containers']):
                            new_bd_num = max_bd_num + 1 + idx
                            new_bd_id = f"BD{new_bd_num:04d}"
                            rows_to_append.append({
                                "Detail ID": new_bd_id,
                                "Booking ID": new_bk_id,
                                "Container Type": item.get("Container Type"),
                                "Number": item.get("Number")
                            })
                            
                        if rows_to_append:
                            append_records_bulk('Booking_Detail', rows_to_append)
                            
                        # สร้างไฟล์ PDF ฉบับสมบูรณ์สำหรับเก็บไว้ใน Session ให้ผู้ใช้กดดาวน์โหลด
                        final_bk_row = header_record.copy()
                        final_df_bd = pd.DataFrame(rows_to_append)
                        final_pdf_bytes = create_booking_confirmation_pdf(final_bk_row, final_df_bd, df_sender)
                        
                        st.session_state['last_created_bk'] = {
                            "id": new_bk_id,
                            "no": bk_no,
                            "pdf": final_pdf_bytes
                        }
                        
                        st.session_state['containers'] = []
                        st.session_state['reset_key'] += 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาดในการบันทึก: {e}")

    # --- ย่อย 2: ค้นหาและแก้ไข Booking ---
    with sub_bk2:
        st.markdown("#### ค้นหาและจัดการข้อมูล Booking")
        df_bk_all = get_data_from_sheet('Booking_Header')
        if df_bk_all.empty:
            st.info("ยังไม่มีข้อมูล Booking ในระบบ")
        else:
            search_bk_val = st.text_input("ค้นหาจาก Booking ID หรือ Booking Number")
            filtered_bks = df_bk_all
            if search_bk_val:
                filtered_bks = df_bk_all[
                    df_bk_all['Booking ID'].astype(str).str.contains(search_bk_val, case=False, na=False) |
                    df_bk_all['Booking Number'].astype(str).str.contains(search_bk_val, case=False, na=False)
                ]
            
            if filtered_bks.empty:
                st.warning("ไม่พบข้อมูล Booking ที่ตรงตามคำค้นหา")
            else:
                bk_list_opts = filtered_bks.apply(lambda r: f"{r['Booking ID']} - {r.get('Booking Number', '-')} - {r.get('Customer', '-')}", axis=1).tolist()
                sel_bk_opt = st.selectbox("เลือก Booking:", bk_list_opts)
                sel_bk_id = sel_bk_opt.split(" - ")[0]
                bk_data = df_bk_all[df_bk_all['Booking ID'] == sel_bk_id].iloc[0]
                
                # ดึงรายละเอียดตู้
                df_bd_all = get_data_from_sheet('Booking_Detail')
                if not df_bd_all.empty and 'Booking ID' in df_bd_all.columns:
                    bk_containers = df_bd_all[df_bd_all['Booking ID'] == sel_bk_id]
                else:
                    bk_containers = pd.DataFrame()
                
                # แสดง PDF Download และปุ่มส่งข้อมูลไปคำนวณต้นทุน-กำไร
                st.markdown("---")
                pdf_data = create_booking_confirmation_pdf(bk_data, bk_containers, df_sender)
                
                col_edit_btn_1, col_edit_btn_2 = st.columns(2)
                with col_edit_btn_1:
                    st.download_button(
                        label="📄 ดาวน์โหลด Booking Confirmation PDF",
                        data=pdf_data,
                        file_name=f"{bk_data.get('Booking Number', 'BK')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"dl_bk_btn_{sel_bk_id}"
                    )
                with col_edit_btn_2:
                    if st.button("💰 ส่งข้อมูลไปคำนวณต้นทุน-กำไร", use_container_width=True, key=f"send_costing_btn_{sel_bk_id}"):
                        target_opt = None
                        for opt in bk_opts_costing_global:
                            if opt.startswith(sel_bk_id + " - "):
                                target_opt = opt
                                break
                        if target_opt:
                            st.session_state["costing_bk_select"] = target_opt
                            st.session_state['show_costing_sent_success'] = True
                            st.rerun()

                if st.session_state.get('show_costing_sent_success'):
                    st.success(f"ส่งข้อมูล Booking {sel_bk_id} ไปยังหน้าคำนวณต้นทุน-กำไรเรียบร้อยแล้ว! กรุณาคลิกแท็บ '💰 คำนวณต้นทุน-กำไร' ด้านบน เพื่อดูข้อมูล")
                    if st.button("ตกลง", key="clear_costing_sent_success"):
                        st.session_state['show_costing_sent_success'] = False
                        st.rerun()

                
                # โหลดรายการตู้ใน session_state เพื่อแก้ไข
                if 'current_edit_bk_id' not in st.session_state or st.session_state['current_edit_bk_id'] != sel_bk_id:
                    st.session_state['current_edit_bk_id'] = sel_bk_id
                    if not bk_containers.empty:
                        st.session_state['edit_containers'] = bk_containers[['Container Type', 'Number']].to_dict('records')
                    else:
                        st.session_state['edit_containers'] = []

                st.markdown(f"### 📝 แก้ไขข้อมูล Booking: {sel_bk_id}")
                
                # --- ส่วนที่ 1: ข้อมูลทั่วไป ---
                st.markdown("#### 1. ข้อมูลทั่วไป (General Info)")
                e_r1_1, e_r1_2, e_r1_3 = st.columns([1, 2, 1])
                with e_r1_1: 
                    e_bk_date = st.date_input("Booking Date", value=p_date(bk_data.get('Booking Date')), format="DD/MM/YYYY", key=f"e_bk_date_{sel_bk_id}")
                with e_r1_2: 
                    e_cust = st.selectbox("Customer", cust_opts, index=cust_opts.index(safe_str(bk_data.get('Customer'))) if safe_str(bk_data.get('Customer')) in cust_opts else None, key=f"e_bk_cust_{sel_bk_id}")
                with e_r1_3: 
                    e_contact = st.text_input("Contact Person", value=safe_str(bk_data.get('Contact Person')), key=f"e_bk_contact_{sel_bk_id}")

                e_r2_1, e_r2_2, e_r2_3 = st.columns([2, 1, 1])
                with e_r2_1: 
                    e_commodity = st.text_input("Commodity", value=safe_str(bk_data.get('Commodity')), key=f"e_bk_commodity_{sel_bk_id}")
                with e_r2_2: 
                    e_weight = st.number_input("Weight (Kg)", format="%.2f", value=safe_float(bk_data.get('Weight')), key=f"e_bk_weight_{sel_bk_id}")
                with e_r2_3: 
                    e_meas = st.number_input("Measurement (CBM)", format="%.2f", value=safe_float(bk_data.get('Measurement')), key=f"e_bk_measurement_{sel_bk_id}")

                e_r3_1, e_r3_2 = st.columns([1, 1])
                with e_r3_1: 
                    e_bk_no = st.text_input("Booking Number", value=safe_str(bk_data.get('Booking Number')), key=f"e_bk_no_{sel_bk_id}")
                with e_r3_2: 
                    e_bl_no = st.text_input("B/L Number", value=safe_str(bk_data.get('B/L Number')), key=f"e_bk_bl_no_{sel_bk_id}")

                e_r4_1, e_r4_2 = st.columns([1, 1])
                with e_r4_1: 
                    e_sender = st.selectbox("Sender", sender_opts, index=sender_opts.index(safe_str(bk_data.get('Sender'))) if safe_str(bk_data.get('Sender')) in sender_opts else None, key=f"e_bk_sender_{sel_bk_id}")
                with e_r4_2:
                    e_sender_phone = ""
                    if e_sender and not df_sender.empty:
                        match = df_sender[df_sender['Sender Name'].astype(str) == e_sender]
                        if not match.empty: e_sender_phone = safe_str(match.iloc[0].get('Sender Phone'))
                    st.text_input("Sender Phone", value=e_sender_phone, disabled=True, key=f"e_show_s_phone_{sel_bk_id}")

                # --- ส่วนที่ 2: รายการบรรจุสินค้า ---
                st.divider()
                st.markdown("#### 2. แก้ไขรายการตู้คอนเทนเนอร์/LCL")
                e_ct_1, e_ct_2, e_ct_3 = st.columns([2, 2, 1])
                with e_ct_1:
                    ct_opts = [safe_str(x) for x in df_ct['Container Type'].dropna().tolist()] if not df_ct.empty else []
                    e_sel_ct = st.selectbox("Type", ct_opts, index=None, key=f"e_bk_sel_ct_{sel_bk_id}")
                with e_ct_2: 
                    e_qty = st.number_input("QTY (จำนวนตู้ หรือระบุ 1 สำหรับ LCL)", min_value=1, step=1, value=None, key=f"e_bk_qty_{sel_bk_id}")
                with e_ct_3:
                    st.write("") 
                    if st.button("➕ เพิ่มรายการตู้/LCL (แก้ไข)", use_container_width=True, key=f"e_btn_add_{sel_bk_id}"):
                        if e_sel_ct and e_qty:
                            st.session_state['edit_containers'].append({"Container Type": e_sel_ct, "Number": e_qty})
                            st.rerun()

                if st.session_state['edit_containers']:
                    st.table(st.session_state['edit_containers'])
                    if st.button("❌ ล้างรายการบรรจุ (แก้ไข)", key=f"e_btn_clear_{sel_bk_id}"):
                        st.session_state['edit_containers'] = []
                        st.rerun()

                # --- ส่วนที่ 3: เส้นทางและเรือ ---
                st.divider()
                st.markdown("#### 3. เส้นทางและเรือ (Routing & Vessel)")
                e_rv1_1, e_rv1_2 = st.columns([3, 1])
                with e_rv1_1: 
                    e_pl = st.selectbox("Port Loading", pl_opts, index=pl_opts.index(safe_str(bk_data.get('Port Loading'))) if safe_str(bk_data.get('Port Loading')) in pl_opts else None, key=f"e_bk_pl_{sel_bk_id}")
                with e_rv1_2:
                    e_paperless = ""
                    if e_pl and not df_pl.empty:
                        match = df_pl[df_pl['Port Name'].astype(str) == e_pl]
                        if not match.empty: e_paperless = safe_str(match.iloc[0].get('Paperless Code'))
                    st.text_input("Paperless Code", value=e_paperless, disabled=True, key=f"e_show_paperless_{sel_bk_id}")

                e_rv2_1, e_rv2_2 = st.columns([1, 1])
                with e_rv2_1: 
                    e_pd = st.selectbox("Port Discharge", pd_opts, index=pd_opts.index(safe_str(bk_data.get('Port Discharge'))) if safe_str(bk_data.get('Port Discharge')) in pd_opts else None, key=f"e_bk_pd_{sel_bk_id}")
                with e_rv2_2: 
                    e_final_dest = st.text_input("Final Destination", value=safe_str(bk_data.get('Final Destination')), key=f"e_bk_final_dest_{sel_bk_id}")

                e_rv3_1, e_rv3_2 = st.columns([3, 1])
                with e_rv3_1:
                    e_liner = st.selectbox("Liner", liner_opts, index=liner_opts.index(safe_str(bk_data.get('Liner'))) if safe_str(bk_data.get('Liner')) in liner_opts else None, key=f"e_bk_liner_{sel_bk_id}")
                with e_rv3_2:
                    e_liner_tax = ""
                    if e_liner and not df_liner.empty:
                        match = df_liner[df_liner['Liner Name'].astype(str) == e_liner]
                        if not match.empty: e_liner_tax = safe_str(match.iloc[0].get('Liner Tax ID'))
                    st.text_input("Liner Tax ID", value=e_liner_tax, disabled=True, key=f"e_show_liner_tax_{sel_bk_id}")

                e_rv4_1, e_rv4_2 = st.columns([3, 1])
                with e_rv4_1: 
                    e_feeder = st.text_input("Feeder / Voyage", value=safe_str(bk_data.get('Feeder/Voyage')), key=f"e_bk_feeder_{sel_bk_id}")
                with e_rv4_2: 
                    e_etd = st.date_input("ETD", value=p_date(bk_data.get('ETD')), format="DD/MM/YYYY", key=f"e_bk_etd_{sel_bk_id}")

                e_rv5_1, e_rv5_2 = st.columns([3, 1])
                with e_rv5_1: 
                    e_vessel = st.text_input("Vessel / Voyage", value=safe_str(bk_data.get('Vessel/Voyage')), key=f"e_bk_vessel_{sel_bk_id}")
                with e_rv5_2: 
                    e_eta = st.date_input("ETA", value=p_date(bk_data.get('ETA')), format="DD/MM/YYYY", key=f"e_bk_eta_{sel_bk_id}")

                # --- ส่วนที่ 4: วันเวลา Cut Off ---
                st.divider()
                st.markdown("#### 4. วันเวลา Cut Off และสถานที่")
                e_co1_1, e_co1_2 = st.columns([1, 3])
                with e_co1_1: 
                    e_pickup_date = st.date_input("Pick Up Date", value=p_date(bk_data.get('Pick Up Date')), format="DD/MM/YYYY", key=f"e_bk_pickup_date_{sel_bk_id}")
                with e_co1_2: 
                    e_pickup_place = st.text_input("Pick Up Place", value=safe_str(bk_data.get('Pick Up Place')), key=f"e_bk_pickup_place_{sel_bk_id}")

                e_co2_1, e_co2_2 = st.columns([1, 3])
                with e_co2_1: 
                    e_return_date = st.date_input("Return Date", value=p_date(bk_data.get('Return Date')), format="DD/MM/YYYY", key=f"e_bk_return_date_{sel_bk_id}")
                with e_co2_2: 
                    e_return_place = st.text_input("Return Place", value=safe_str(bk_data.get('Return Place')), key=f"e_bk_return_place_{sel_bk_id}")

                e_co3_1, e_co3_2 = st.columns([1, 1])
                with e_co3_1: 
                    e_cy_date = st.date_input("Container Cut Off Date", value=p_date(bk_data.get('Container Cut Off Date')), format="DD/MM/YYYY", key=f"e_bk_cy_date_{sel_bk_id}")
                with e_co3_2: 
                    e_cy_time = st.time_input("Container Cut Off Time", value=p_time(bk_data.get('Container Cut Off Time')), key=f"e_bk_cy_time_{sel_bk_id}")

                e_co4_1, e_co4_2 = st.columns([1, 1])
                with e_co4_1: 
                    e_si_date = st.date_input("S/I Cut Off Date", value=p_date(bk_data.get('S/I Cut Off Date')), format="DD/MM/YYYY", key=f"e_bk_si_date_{sel_bk_id}")
                with e_co4_2: 
                    e_si_time = st.time_input("S/I Cut Off Time", value=p_time(bk_data.get('S/I Cut Off Time')), key=f"e_bk_si_time_{sel_bk_id}")

                e_co5_1, e_co5_2 = st.columns([1, 1])
                with e_co5_1: 
                    e_vgm_date = st.date_input("VGM Cut Off Date", value=p_date(bk_data.get('VGM Cut Off Date')), format="DD/MM/YYYY", key=f"e_bk_vgm_date_{sel_bk_id}")
                with e_co5_2: 
                    e_vgm_time = st.time_input("VGM Cut Off Time", value=p_time(bk_data.get('VGM Cut Off Time')), key=f"e_bk_vgm_time_{sel_bk_id}")

                e_co6_1, e_co6_2 = st.columns([1, 1])
                with e_co6_1: 
                    e_bl_date = st.date_input("B/L Cut Off Date", value=p_date(bk_data.get('B/L Cut Off Date')), format="DD/MM/YYYY", key=f"e_bk_bl_date_{sel_bk_id}")
                with e_co6_2: 
                    e_bl_time = st.time_input("B/L Cut Off Time", value=p_time(bk_data.get('B/L Cut Off Time')), key=f"e_bk_bl_time_{sel_bk_id}")

                e_co7_1, e_co7_2 = st.columns([1, 1])
                with e_co7_1: 
                    e_first_return = st.date_input("First Return Date", value=p_date(bk_data.get('First Return Date')), format="DD/MM/YYYY", key=f"e_bk_first_return_{sel_bk_id}")

                e_remark = st.text_area("Remark", value=safe_str(bk_data.get('Remark')), key=f"e_bk_remark_{sel_bk_id}")

                st.divider()
                if st.button("💾 บันทึกการแก้ไขข้อมูล Booking", type="primary", use_container_width=True, key=f"e_btn_save_{sel_bk_id}"):
                    if not st.session_state['edit_containers']:
                        st.error("กรุณาเพิ่มรายการตู้คอนเทนเนอร์/LCL อย่างน้อย 1 รายการก่อนบันทึกครับ")
                    else:
                        with st.spinner("กำลังบันทึกการแก้ไขข้อมูล..."):
                            try:
                                update_fields = {
                                    "Booking Date": fmt_date(e_bk_date),
                                    "Booking Number": safe_str(e_bk_no),
                                    "B/L Number": safe_str(e_bl_no),
                                    "Customer": e_cust,
                                    "Contact Person": e_contact,
                                    "Commodity": e_commodity,
                                    "Weight": e_weight,
                                    "Measurement": e_meas,
                                    "Liner": e_liner,
                                    "Liner Tax ID": e_liner_tax,
                                    "Port Loading": e_pl,
                                    "Paperless Code": e_paperless,
                                    "Port Discharge": e_pd,
                                    "Final Destination": e_final_dest,
                                    "Feeder/Voyage": e_feeder,
                                    "ETD": fmt_date(e_etd),
                                    "Vessel/Voyage": e_vessel,
                                    "ETA": fmt_date(e_eta),
                                    "Pick Up Date": fmt_date(e_pickup_date),
                                    "Pick Up Place": e_pickup_place,
                                    "Return Date": fmt_date(e_return_date),
                                    "Return Place": e_return_place,
                                    "Container Cut Off Date": fmt_date(e_cy_date),
                                    "Container Cut Off Time": fmt_time(e_cy_time),
                                    "VGM Cut Off Date": fmt_date(e_vgm_date),
                                    "VGM Cut Off Time": fmt_time(e_vgm_time),
                                    "S/I Cut Off Date": fmt_date(e_si_date),
                                    "S/I Cut Off Time": fmt_time(e_si_time),
                                    "B/L Cut Off Date": fmt_date(e_bl_date),
                                    "B/L Cut Off Time": fmt_time(e_bl_time),
                                    "First Return Date": fmt_date(e_first_return),
                                    "Remark": e_remark,
                                    "Sender": e_sender
                                }
                                update_record('Booking_Header', bk_data['airtable_record_id'], update_fields)
                                
                                # 2. ลบรายละเอียดตู้เก่าออกทั้งหมด
                                if not bk_containers.empty and 'Detail ID' in bk_containers.columns:
                                    existing_detail_ids = bk_containers['airtable_record_id'].dropna().tolist()
                                    if existing_detail_ids:
                                        delete_records_bulk('Booking_Detail', existing_detail_ids)
                                        
                                # 3. บันทึกรายละเอียดตู้ใหม่เข้าไป
                                max_bd_num = 0
                                df_bd = get_data_from_sheet('Booking_Detail')
                                if not df_bd.empty and 'Detail ID' in df_bd.columns:
                                    for val in df_bd['Detail ID'].dropna():
                                        v_str = safe_str(val)
                                        if v_str.startswith('BD'):
                                            try:
                                                num = int(v_str.replace('BD', ''))
                                                if num > max_bd_num: max_bd_num = num
                                            except: pass
                                            
                                rows_to_append = []
                                for idx, item in enumerate(st.session_state['edit_containers']):
                                    new_bd_num = max_bd_num + 1 + idx
                                    new_bd_id = f"BD{new_bd_num:04d}"
                                    rows_to_append.append({
                                        "Detail ID": new_bd_id,
                                        "Booking ID": sel_bk_id,
                                        "Container Type": item.get("Container Type"),
                                        "Number": item.get("Number")
                                    })
                                    
                                if rows_to_append:
                                    append_records_bulk('Booking_Detail', rows_to_append)
                                    
                                st.success("แก้ไขข้อมูล Booking และรายละเอียดตู้เรียบร้อยแล้ว!")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"เกิดข้อผิดพลาดในการบันทึกการแก้ไข: {e}")

    # --- ย่อย 3: Job Costing (คำนวณต้นทุน-กำไร) ---
    with sub_bk3:
        st.markdown("#### Job Costing - บริหารต้นทุนและราคาขาย")
        df_bk_all = df_bk_all_global
        if df_bk_all.empty:
            st.info("ยังไม่มีข้อมูล Booking ในระบบ")
        else:
            if 'costing_bk_select' not in st.session_state or st.session_state['costing_bk_select'] not in bk_opts_costing_global:
                st.session_state['costing_bk_select'] = bk_opts_costing_global[0]
            
            sel_bk_costing = st.selectbox("เลือก Job / Booking สำหรับระบุต้นทุน:", bk_opts_costing_global, key="costing_bk_select")
            sel_bk_id = sel_bk_costing.split(" - ")[0]
            
            # ดึงข้อมูล Booking ที่เลือก
            bk_info = df_bk_all[df_bk_all['Booking ID'] == sel_bk_id].iloc[0]
            st.info(f"🚢 ลูกค้า: {bk_info.get('Customer')} | สินค้า: {bk_info.get('Commodity')} | เส้นทาง: {bk_info.get('Port Loading')} -> {bk_info.get('Port Discharge')}")
            
            # โหลดตาราง Job_Costing
            df_costing_all = get_data_from_sheet('Job_Costing')
            
            # ฟอร์มเพิ่มรายการ Costing
            st.markdown("---")
            st.markdown("##### ➕ เพิ่มรายการบัญชีงบภายใน")
            
            # 1. ดึงข้อมูล container types ของ Booking นี้
            df_booking_details = get_data_from_sheet('Booking_Detail')
            if not df_booking_details.empty and 'Booking ID' in df_booking_details.columns:
                booking_containers = df_booking_details[df_booking_details['Booking ID'].astype(str) == safe_str(sel_bk_id)]
            else:
                booking_containers = pd.DataFrame()

            if not booking_containers.empty and 'Container Type' in booking_containers.columns:
                c_ct_opts = [safe_str(x) for x in booking_containers['Container Type'].dropna().unique().tolist() if safe_str(x)]
            else:
                c_ct_opts = []

            if "- (Per Shipment)" not in c_ct_opts:
                c_ct_opts.insert(0, "- (Per Shipment)")
                
            if len(c_ct_opts) == 1:
                c_ct_opts.append("LCL")
                
            # สร้างตัวแปร session_state สำหรับล้างฟอร์ม
            cost_form_k = f"job_cost_key_{sel_bk_id}"
            if cost_form_k not in st.session_state:
                st.session_state[cost_form_k] = 0
            k_idx = st.session_state[cost_form_k]

            with st.form(f"jc_form_{k_idx}", clear_on_submit=True):
                st.markdown("##### 2. รายละเอียดราคาและประเภทบริการ")
                # แถวที่ 1
                col1, col2, col3 = st.columns([4, 3, 2])
                with col1:
                    c_charge_opts = [safe_str(x) for x in get_data_from_sheet('Charge Item')['Charge Item'].dropna().tolist()] if not get_data_from_sheet('Charge Item').empty else []
                    specified_order = ["ocean freight", "thc", "seal fee", "bl fee", "surrender fee", "afr", "ens", "ams", "kb", "amendment fee", "handling fee"]
                    c_charge_opts = list(set(c_charge_opts))
                    def get_charge_sort_key(item):
                        item_lower = item.lower().strip()
                        if item_lower in specified_order:
                            return (0, specified_order.index(item_lower), item_lower)
                        return (1, 0, item_lower)
                    c_charge_opts.sort(key=get_charge_sort_key)
                    cost_charge = st.selectbox("Charge Item (รายการ)", c_charge_opts, placeholder="-- เลือกค่าบริการ --")
                with col2:
                    cost_ctype = st.selectbox("Container Type (ชนิดตู้)", c_ct_opts)
                
                # คำนวณ default_qty ตาม cost_ctype
                default_qty = 1.0
                if cost_ctype == "LCL":
                    weight_kg = safe_float(bk_info.get('Weight'), 0.0)
                    measurement_cbm = safe_float(bk_info.get('Measurement'), 0.0)
                    default_qty = max(weight_kg / 1000.0, measurement_cbm)
                    if default_qty == 0:
                        default_qty = 1.0
                elif not booking_containers.empty and 'Container Type' in booking_containers.columns:
                    match_ctype = booking_containers[booking_containers['Container Type'].astype(str) == safe_str(cost_ctype)]
                    if not match_ctype.empty:
                        default_qty = safe_float(match_ctype.iloc[0].get('Number', 1.0), 1.0)
                
                with col3:
                    cost_qty = st.number_input("QTY (จำนวน)", min_value=0.01, value=float(default_qty), step=1.0)

                # แถวที่ 2
                col2_1, col2_2, col2_3, col2_4, col2_5, col2_6 = st.columns([2, 3, 2, 2, 3, 2])
                with col2_1:
                    cost_curr = st.selectbox("Cost Cur.", curr_opts, index=curr_opts.index('THB') if 'THB' in curr_opts else 0)
                with col2_2:
                    cost_price = st.number_input("Cost Price (ทุน/หน่วย)", min_value=0.0, step=100.0)
                with col2_3:
                    cost_ex = st.number_input("Cost Exc.", min_value=0.0, value=1.0, step=0.1, format="%.4f")
                with col2_4:
                    sell_curr = st.selectbox("Sell Cur.", curr_opts, index=curr_opts.index('THB') if 'THB' in curr_opts else 0)
                with col2_5:
                    sell_price = st.number_input("Sell Price (ขาย/หน่วย)", min_value=0.0, step=100.0)
                with col2_6:
                    sell_ex = st.number_input("Sell Exc.", min_value=0.0, value=1.0, step=0.1, format="%.4f")

                # แถวที่ 3
                col3_1, col3_2, col3_3 = st.columns([6, 2, 2])
                with col3_1:
                    cost_remark = st.text_input("หมายเหตุ (Remark)")
                with col3_2:
                    st.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True)
                    cost_reimb = st.checkbox("จ่ายแทน (Reimb.)")
                with col3_3:
                    st.markdown("<div style='padding-top: 24px;'></div>", unsafe_allow_html=True)
                    submit_btn = st.form_submit_button("➕ บันทึกรายการ", use_container_width=True)
            
            if submit_btn:
                if not cost_charge:
                    st.error("กรุณาระบุ Charge Item")
                else:
                    new_cost_id = generate_next_id('Job_Costing', 'Costing ID', 'JC')
                    cost_rec = {
                        "Costing ID": new_cost_id,
                        "Booking ID": sel_bk_id,
                        "Customer": bk_info.get('Customer'),
                        "Supplier": "",
                        "Charge Item": cost_charge,
                        "Container Type": cost_ctype,
                        "Quantity": cost_qty,
                        "Cost Price": cost_price,
                        "Cost Currency": cost_curr,
                        "Cost Exchange Rate": cost_ex,
                        "Selling Price": sell_price,
                        "Selling Currency": sell_curr,
                        "Selling Exchange Rate": sell_ex,
                        "Reimbursement": cost_reimb,
                        "Remark": cost_remark
                    }
                    append_record('Job_Costing', cost_rec)
                    st.success("บันทึกต้นทุนเสร็จสมบูรณ์!")
                    st.session_state[cost_form_k] += 1
                    st.rerun()

            # แสดงตาราง Costing ปัจจุบัน
            st.markdown("---")
            st.markdown("##### 📝 รายการงบกำไรขาดทุนปัจจุบัน")
            if not df_costing_all.empty and 'Booking ID' in df_costing_all.columns:
                job_costs = df_costing_all[df_costing_all['Booking ID'] == sel_bk_id]
                if not job_costs.empty:
                    # คำนวณรายได้/ต้นทุนเป็น THB
                    job_costs['Total Cost (THB)'] = job_costs.apply(lambda r: safe_float(r['Cost Price']) * safe_float(r['Cost Exchange Rate']) * safe_float(r['Quantity']), axis=1)
                    job_costs['Total Selling (THB)'] = job_costs.apply(lambda r: safe_float(r['Selling Price']) * safe_float(r['Selling Exchange Rate']) * safe_float(r['Quantity']), axis=1)
                    job_costs['Profit (THB)'] = job_costs['Total Selling (THB)'] - job_costs['Total Cost (THB)']
                    
                    # ตกแต่งหัวตารางของ DataFrame ให้ตรงตามความคุ้นเคย
                    display_df = job_costs.copy()
                    if 'Reimbursement' not in display_df.columns:
                        display_df['Reimbursement'] = False
                    if 'Remark' not in display_df.columns:
                        display_df['Remark'] = ""
                    display_df['จ่ายแทน'] = display_df['Reimbursement'].apply(lambda x: "✔️ จ่ายแทน" if x else "")
                    
                    # เติม No. ตามลำดับแถว
                    display_df = display_df.reset_index(drop=True)
                    display_df['No.'] = display_df.index + 1
                    
                    st.dataframe(
                        display_df[['No.', 'Charge Item', 'Quantity', 'Container Type', 'จ่ายแทน', 'Cost Price', 'Cost Currency', 'Cost Exchange Rate', 'Total Cost (THB)', 'Selling Price', 'Selling Currency', 'Selling Exchange Rate', 'Total Selling (THB)']],
                        column_config={
                            "No.": "No.",
                            "Charge Item": "Charge Item",
                            "Quantity": "QTY",
                            "Container Type": "Type",
                            "จ่ายแทน": "จ่ายแทน (Reimb.)",
                            "Cost Price": "Cost Price",
                            "Cost Currency": "Cost Cur.",
                            "Cost Exchange Rate": "Cost Exc",
                            "Total Cost (THB)": "รวมทุน(THB)",
                            "Selling Price": "Selling Price",
                            "Selling Currency": "Sell Cur.",
                            "Selling Exchange Rate": "Sell Exc",
                            "Total Selling (THB)": "รวมขาย(THB)"
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # แสดง Metric รวม
                    total_c = job_costs['Total Cost (THB)'].sum()
                    total_s = job_costs['Total Selling (THB)'].sum()
                    total_p = job_costs['Profit (THB)'].sum()
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("ยอดรวมต้นทุน (Total Cost)", f"{total_c:,.2f} THB")
                    m2.metric("ยอดรวมรายได้ (Total Selling)", f"{total_s:,.2f} THB")
                    m3.metric("กำไรเบื้องต้น (Gross Profit)", f"{total_p:,.2f} THB", delta=f"{(total_p / total_s * 100 if total_s > 0 else 0):.1f}% Profit Margin")
                    
                    # ปุ่มลบรายการ Costing
                    st.markdown("---")
                    del_opts = job_costs.apply(lambda r: f"{r['Charge Item']} ({r['Costing ID']})", axis=1).tolist()
                    sel_del_opt = st.selectbox("เลือกรายการที่จะลบ:", del_opts)
                    del_cost_id = sel_del_opt.split("(")[-1].replace(")", "").strip()
                    col_del_1, col_del_2 = st.columns(2)
                    with col_del_1:
                        if st.button("❌ ลบรายการ Costing ที่เลือก", type="primary", use_container_width=True):
                            target_rec = job_costs[job_costs['Costing ID'] == del_cost_id].iloc[0]
                            delete_records_bulk('Job_Costing', [target_rec['airtable_record_id']])
                            st.success("ลบรายการ Costing เรียบร้อยแล้ว!")
                            st.rerun()
                    with col_del_2:
                        if st.button("🗑️ ล้างตารางทั้งหมดสำหรับ Job นี้", type="primary", use_container_width=True, key=f"clear_all_costing_{sel_bk_id}"):
                            rec_ids_to_del = job_costs['airtable_record_id'].tolist()
                            delete_records_bulk('Job_Costing', rec_ids_to_del)
                            st.success("ล้างรายการทั้งหมดเรียบร้อยแล้ว!")
                            st.rerun()

                    # ปุ่มส่งต่อไปออกใบแจ้งหนี้
                    st.markdown("---")
                    col_inv_1, col_inv_2 = st.columns([3, 1])
                    with col_inv_1:
                        if st.button("👉 ส่งข้อมูลนี้ไปทำใบแจ้งหนี้ทันที", use_container_width=True, key=f"send_invoice_btn_{sel_bk_id}"):
                            st.session_state["sel_bk_inv_create"] = sel_bk_costing
                            st.session_state['show_invoice_sent_success'] = True
                            st.rerun()
                    with col_inv_2:
                        pass
                        
                    if st.session_state.get('show_invoice_sent_success'):
                        st.success(f"ส่งข้อมูล Booking {sel_bk_id} ไปยังหน้าออกใบแจ้งหนี้เรียบร้อยแล้ว! กรุณาคลิกเมนูด้านซ้ายย้ายไปแท็บ '🧾 ใบแจ้งหนี้ (Invoice)'")
                        if st.button("ตกลง", key="clear_invoice_sent_success"):
                            st.session_state['show_invoice_sent_success'] = False
                            st.rerun()
                else:
                    st.info("ยังไม่มีข้อมูลต้นทุนสำหรับ Job นี้")
            else:
                st.info("ยังไม่มีข้อมูลต้นทุนสำหรับ Job นี้")

# --- Page 3: ใบแจ้งหนี้ (Invoice) ---
elif page == "🧾 ใบแจ้งหนี้ (Invoice)":
    st.header("ระบบออกใบแจ้งหนี้ (Invoice)")
    inv_tab1, inv_tab2 = st.tabs(["🧾 ออกใบแจ้งหนี้ใหม่", "🔍 ค้นหา/พิมพ์ ใบแจ้งหนี้"])
    
    with inv_tab1:
        st.markdown("### 1. เลือกข้อมูล Booking เพื่อออกบิล")
        df_bk_all = df_bk_all_global
        if df_bk_all.empty:
            st.info("ยังไม่มีข้อมูล Booking ในระบบ")
        else:
            if 'sel_bk_inv_create' not in st.session_state or st.session_state['sel_bk_inv_create'] not in bk_opts_costing_global:
                st.session_state['sel_bk_inv_create'] = bk_opts_costing_global[0] if bk_opts_costing_global else None
                
            sel_bk_inv = st.selectbox("เลือก Booking Number:", bk_opts_costing_global, key="sel_bk_inv_create")
            sel_bk_id = sel_bk_inv.split(" - ")[0]
            
            bk_data = df_bk_all[df_bk_all['Booking ID'] == sel_bk_id].iloc[0]
            cust_name = bk_data.get('Customer')
            
            st.info(f"👤 ลูกค้า: {cust_name} | 🚢 Booking No: {bk_data.get('Booking Number', '-')}")
            
            col_date1, col_date2 = st.columns(2)
            with col_date1:
                inv_date = st.date_input("วันที่ออกใบแจ้งหนี้ (Invoice Date)", value=datetime.date.today(), format="DD/MM/YYYY")
            with col_date2:
                due_date = st.date_input("วันครบกำหนดชำระ (Due Date)", value=datetime.date.today() + datetime.timedelta(days=30), format="DD/MM/YYYY")
            
            if 'prev_sel_bk_id_inv' not in st.session_state or st.session_state['prev_sel_bk_id_inv'] != sel_bk_id:
                st.session_state['prev_sel_bk_id_inv'] = sel_bk_id
                df_costs = get_data_from_sheet('Job_Costing')
                job_sales = df_costs[df_costs['Booking ID'] == sel_bk_id] if not df_costs.empty and 'Booking ID' in df_costs.columns else pd.DataFrame()
                
                items_list = []
                if not job_sales.empty:
                    for idx, row in job_sales.reset_index().iterrows():
                        if safe_float(row.get('Selling Price', 0.0)) <= 0:
                            continue
                        is_reimb = False
                        if 'Reimbursement' in row and row['Reimbursement'] is not None:
                            is_reimb = bool(row['Reimbursement'])
                        else:
                            charge_lower = safe_str(row.get('Charge Item')).lower()
                            if 'reimbursement' in charge_lower or 'จ่ายแทน' in charge_lower:
                                is_reimb = True
                        
                        items_list.append({
                            "Charge Item": safe_str(row.get('Charge Item')),
                            "Container Type": safe_str(row.get('Container Type')),
                            "Quantity": safe_float(row.get('Quantity', 1.0)),
                            "Unit Price": safe_float(row.get('Selling Price', 0.0)),
                            "Currency": safe_str(row.get('Selling Currency', 'THB')),
                            "Exchange Rate": safe_float(row.get('Selling Exchange Rate', 1.0)),
                            "VAT Rate (%)": 0.0 if is_reimb else 7.0,
                            "Tax Rate (%)": 0.0 if is_reimb else 1.0,
                            "Reimbursement": is_reimb
                        })
                items_list.sort(key=get_item_sort_key)
                st.session_state['invoice_items'] = items_list

            st.markdown("---")
            st.markdown("### 2. รายการเรียกเก็บเงิน")
            invoice_items = st.session_state.get('invoice_items', [])
            if not invoice_items:
                st.warning("❌ ไม่พบข้อมูลราคาขายสำหรับ Booking นี้ในระบบ Job Costing กรุณาไปเพิ่มราคาขายในระบบ Job Costing ก่อนครับ")
            else:
                h_cols = st.columns([2.0, 1.0, 0.6, 1.2, 1.0, 0.8, 0.9, 0.9, 1.4])
                h_cols[0].markdown("**รายการ**")
                h_cols[1].markdown("**ชนิดตู้**")
                h_cols[2].markdown("**QTY**")
                h_cols[3].markdown("**ราคา**")
                h_cols[4].markdown("**เรทเงิน**")
                h_cols[5].markdown("**จ่ายแทน**")
                h_cols[6].markdown("**VAT %**")
                h_cols[7].markdown("**WHT %**")
                h_cols[8].markdown("**รวม (THB)**")
                
                total_amt = 0.0
                reimb_amt = 0.0
                vat_amt = 0.0
                wht_amt = 0.0
                
                for idx, item in enumerate(invoice_items):
                    r_cols = st.columns([2.0, 1.0, 0.6, 1.2, 1.0, 0.8, 0.9, 0.9, 1.4])
                    r_cols[0].text_input(f"รายการที่ {idx+1}", value=item["Charge Item"], disabled=True, key=f"inv_item_charge_{idx}", label_visibility="collapsed")
                    r_cols[1].text_input(f"ชนิดตู้ {idx+1}", value=item["Container Type"], disabled=True, key=f"inv_item_ctype_{idx}", label_visibility="collapsed")
                    
                    new_qty = r_cols[2].number_input(f"QTY {idx+1}", value=item["Quantity"], min_value=0.0, step=1.0, key=f"inv_item_qty_{idx}", label_visibility="collapsed")
                    item["Quantity"] = new_qty
                    
                    new_price = r_cols[3].number_input(f"ราคา {idx+1} ({item['Currency']})", value=item["Unit Price"], min_value=0.0, step=10.0, key=f"inv_item_price_{idx}", label_visibility="collapsed")
                    item["Unit Price"] = new_price
                    
                    new_ex = r_cols[4].number_input(f"เรทเงิน {idx+1}", value=item["Exchange Rate"], min_value=0.0, step=0.1, format="%.4f", key=f"inv_item_ex_{idx}", label_visibility="collapsed")
                    item["Exchange Rate"] = new_ex
                    
                    new_reimb = r_cols[5].checkbox(f"จ่ายแทน {idx+1}", value=item["Reimbursement"], key=f"inv_item_reimb_{idx}", label_visibility="collapsed")
                    item["Reimbursement"] = new_reimb
                    
                    vat_disabled = new_reimb
                    wht_disabled = new_reimb
                    
                    vat_opts = [0.0, 7.0]
                    if float(item["VAT Rate (%)"]) not in vat_opts:
                        vat_opts.append(float(item["VAT Rate (%)"]))
                    
                    vat_val = 0.0 if new_reimb else float(item["VAT Rate (%)"])
                    new_vat = r_cols[6].selectbox(f"VAT {idx+1}", vat_opts, index=vat_opts.index(vat_val), disabled=vat_disabled, key=f"inv_item_vat_{idx}", label_visibility="collapsed")
                    item["VAT Rate (%)"] = new_vat
                    
                    wht_opts = [0.0, 1.0, 3.0, 5.0]
                    if float(item["Tax Rate (%)"]) not in wht_opts:
                        wht_opts.append(float(item["Tax Rate (%)"]))
                    
                    wht_val = 0.0 if new_reimb else float(item["Tax Rate (%)"])
                    new_wht = r_cols[7].selectbox(f"WHT {idx+1}", wht_opts, index=wht_opts.index(wht_val), disabled=wht_disabled, key=f"inv_item_wht_{idx}", label_visibility="collapsed")
                    item["Tax Rate (%)"] = new_wht
                    
                    sub_total_thb = new_qty * new_price * new_ex
                    r_cols[8].text_input(f"รวม {idx+1}", value=f"{sub_total_thb:,.2f}", disabled=True, key=f"inv_item_total_{idx}", label_visibility="collapsed")
                    
                    if item["Reimbursement"]:
                        reimb_amt += sub_total_thb
                    else:
                        total_amt += sub_total_thb
                        vat_amt += sub_total_thb * (new_vat / 100.0)
                        wht_amt += sub_total_thb * (new_wht / 100.0)

                st.markdown("---")
                total_amt = round_half_up(total_amt, 2)
                vat_amt = round_half_up(vat_amt, 2)
                wht_amt = round_half_up(wht_amt, 2)
                reimb_amt = round_half_up(reimb_amt, 2)
                grand_total = round_half_up(total_amt + vat_amt - wht_amt + reimb_amt, 2)
                
                col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
                col_m1.metric("มูลค่าบริการ", f"{total_amt:,.2f} THB")
                col_m2.metric("VAT", f"{vat_amt:,.2f} THB")
                col_m3.metric("WHT", f"{wht_amt:,.2f} THB")
                col_m4.metric("จ่ายแทน (Reimb.)", f"{reimb_amt:,.2f} THB")
                col_m5.metric("ยอดรวมชำระสุทธิ", f"{grand_total:,.2f} THB")
                
                st.markdown("---")
                inv_remark = st.text_area("หมายเหตุเพิ่มเติมในใบแจ้งหนี้ (Remark)", key="inv_remark_create_input")
                
                if st.button("💾 บันทึกใบแจ้งหนี้", type="primary", use_container_width=True):
                    try:
                        new_inv_id = generate_next_year_id('Invoice_Header', 'Invoice ID', 'ROC')
                        inv_details = []
                        max_ind_num = 0
                        df_ind = get_data_from_sheet('Invoice_Detail')
                        if not df_ind.empty and 'Invoice Detail ID' in df_ind.columns:
                            for val in df_ind['Invoice Detail ID'].dropna():
                                v_str = safe_str(val)
                                if v_str.startswith('IND'):
                                    try:
                                        num = int(v_str.replace('IND', ''))
                                        if num > max_ind_num: max_ind_num = num
                                    except: pass

                        for idx, item in enumerate(invoice_items):
                            sub_total_thb = item["Quantity"] * item["Unit Price"] * item["Exchange Rate"]
                            new_ind_id = f"IND{(max_ind_num + 1 + idx):04d}"
                            inv_details.append({
                                "Invoice Detail ID": new_ind_id,
                                "Invoice ID": new_inv_id,
                                "Booking ID": sel_bk_id,
                                "Charge Item": item["Charge Item"],
                                "Container Type": item["Container Type"],
                                "Quantity": item["Quantity"],
                                "Unit Price": item["Unit Price"],
                                "Currency": item["Currency"],
                                "Exchange Rate": item["Exchange Rate"],
                                "Amount": sub_total_thb,
                                "VAT Rate (%)": item["VAT Rate (%)"],
                                "Tax Rate (%)": item["Tax Rate (%)"],
                                "Reimbursement": item["Reimbursement"]
                            })
                        
                        header_rec = {
                            "Invoice ID": new_inv_id,
                            "Invoice Date": fmt_date(inv_date),
                            "Due Date": fmt_date(due_date),
                            "Booking ID": sel_bk_id,
                            "Customer ID": bk_data.get('Customer ID', ''),
                            "Customer Name": cust_name,
                            "Total Amount": total_amt,
                            "VAT Amount": vat_amt,
                            "WHT Amount": wht_amt,
                            "Reimbursement Amount": reimb_amt,
                            "Grand Total": grand_total,
                            "Status": "ค้างชำระ"
                        }
                        
                        append_record('Invoice_Header', header_rec)
                        append_records_bulk('Invoice_Detail', inv_details)
                        
                        st.success(f"🎉 สร้างใบแจ้งหนี้ {new_inv_id} สำเร็จเรียบร้อยแล้ว!")
                        
                        st.session_state['invoice_items'] = None
                        st.session_state['prev_sel_bk_id_inv'] = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาดในการบันทึกใบแจ้งหนี้: {e}")
    with inv_tab2:
        df_inv_all = get_data_from_sheet('Invoice_Header')
        if df_inv_all.empty:
            st.info("ยังไม่มีข้อมูลใบแจ้งหนี้ในระบบ")
        else:
            # Create mapping from booking ID to booking number
            # Create mapping from booking ID to booking number and B/L number
            bk_id_to_num = {}
            bk_id_to_bl = {}
            if not df_bk_all_global.empty and 'Booking ID' in df_bk_all_global.columns:
                for _, bk_r in df_bk_all_global.iterrows():
                    b_id = safe_str(bk_r.get('Booking ID'))
                    b_num = safe_str(bk_r.get('Booking Number'))
                    b_bl = safe_str(bk_r.get('B/L Number'))
                    if b_id:
                        bk_id_to_num[b_id] = b_num
                        bk_id_to_bl[b_id] = b_bl
            
            # Format: Invoice ID | BKG ID: Booking ID | Booking No: Booking Number | B/L: B/L Number | ลูกค้า: Customer Name
            inv_opts = []
            for idx, r in df_inv_all.iterrows():
                inv_id_val = safe_str(r['Invoice ID'])
                bk_id_val = safe_str(r.get('Booking ID'))
                bk_num_val = bk_id_to_num.get(bk_id_val, '-') if bk_id_val else '-'
                bl_num_val = bk_id_to_bl.get(bk_id_val, '-') if bk_id_val else '-'
                cust_name_val = safe_str(r.get('Customer Name'))
                inv_opts.append(f"{inv_id_val} | BKG ID: {bk_id_val if bk_id_val else '-'} | Booking No: {bk_num_val} | B/L: {bl_num_val} | ลูกค้า: {cust_name_val}")
                
            sel_inv_opt = st.selectbox("เลือกใบแจ้งหนี้ที่ต้องการจัดการ:", inv_opts, key="sel_inv_opt_edit")
            sel_inv_id = sel_inv_opt.split(" | ")[0].strip()
            
            # โหลดข้อมูลจริง
            inv_row = df_inv_all[df_inv_all['Invoice ID'] == sel_inv_id].iloc[0]
            bk_id = inv_row.get('Booking ID')
            df_bk_all = df_bk_all_global
            bk_row = df_bk_all[df_bk_all['Booking ID'] == bk_id].iloc[0] if not df_bk_all.empty and bk_id in df_bk_all['Booking ID'].values else None
            
            # ตรวจสอบการสลับใบแจ้งหนี้เพื่อโหลดข้อมูลเข้า session state
            if 'prev_sel_inv_id' not in st.session_state or st.session_state['prev_sel_inv_id'] != sel_inv_id:
                st.session_state['prev_sel_inv_id'] = sel_inv_id
                
                # โหลดวันที่
                st.session_state['inv_date_edit'] = p_date(inv_row.get('Invoice Date')) or datetime.date.today()
                st.session_state['due_date_edit'] = p_date(inv_row.get('Due Date')) or (datetime.date.today() + datetime.timedelta(days=30))
                st.session_state['reload_costing_checkbox_edit'] = False
                st.session_state['prev_reload_costing_edit'] = False
                
                # โหลดรายการจาก Invoice_Detail
                df_ind_all = get_data_from_sheet('Invoice_Detail')
                inv_dtl = df_ind_all[df_ind_all['Invoice ID'] == sel_inv_id] if not df_ind_all.empty else pd.DataFrame()
                
                items_list = []
                if not inv_dtl.empty:
                    for idx, row in inv_dtl.iterrows():
                        if safe_float(row.get('Unit Price', 0.0)) <= 0 and safe_float(row.get('Amount', 0.0)) <= 0:
                            continue
                        items_list.append({
                            "Invoice Detail ID": row.get("Invoice Detail ID"),
                            "Charge Item": safe_str(row.get('Charge Item')),
                            "Container Type": safe_str(row.get('Container Type')),
                            "Quantity": safe_float(row.get('Quantity', 1.0)),
                            "Unit Price": safe_float(row.get('Unit Price', 0.0)),
                            "Currency": safe_str(row.get('Currency', 'THB')),
                            "Exchange Rate": safe_float(row.get('Exchange Rate', 1.0)),
                            "VAT Rate (%)": safe_float(row.get('VAT Rate (%)', 7.0)),
                            "Tax Rate (%)": safe_float(row.get('Tax Rate (%)', 1.0)),
                            "Reimbursement": bool(row.get('Reimbursement', False))
                        })
                items_list.sort(key=get_item_sort_key)
                st.session_state['invoice_items_edit'] = items_list

            st.write("---")
            st.info(f"🧾 กำลังแก้ไข Invoice: {sel_inv_id} | ลูกค้า: {inv_row.get('Customer Name', '-')} | สถานะ: {inv_row.get('Status', '-')}")
            
            # ฟอร์มเลือกวันที่ออกใบแจ้งหนี้ และวันครบกำหนดชำระ
            col_date1, col_date2 = st.columns(2)
            with col_date1:
                inv_date_edit = st.date_input("วันที่ออกใบแจ้งหนี้ (Invoice Date)", value=st.session_state['inv_date_edit'], format="DD/MM/YYYY", key="inv_date_edit_input")
                st.session_state['inv_date_edit'] = inv_date_edit
            with col_date2:
                due_date_edit = st.date_input("วันครบกำหนดชำระ (Due Date)", value=st.session_state['due_date_edit'], format="DD/MM/YYYY", key="due_date_edit_input")
                st.session_state['due_date_edit'] = due_date_edit
                
            # โหลดข้อมูลใหม่จาก Job Costing & ปุ่มลบใบแจ้งหนี้
            col_ctrl_1, col_ctrl_2 = st.columns([3, 1])
            with col_ctrl_1:
                reload_costing = st.checkbox("🔄 โหลดข้อมูลใหม่จาก Job Costing", value=st.session_state.get('reload_costing_checkbox_edit', False), key="reload_costing_edit_chk")
                st.session_state['reload_costing_checkbox_edit'] = reload_costing
            with col_ctrl_2:
                delete_btn = st.button("🗑️ ลบใบแจ้งหนี้ทิ้ง", type="primary", use_container_width=True, key="delete_invoice_edit_btn")
                
            # ลอจิกโหลดราคาขายใหม่จาก Job Costing หากติ๊กถูก
            if reload_costing and not st.session_state.get('prev_reload_costing_edit', False):
                df_costs = get_data_from_sheet('Job_Costing')
                job_sales = df_costs[df_costs['Booking ID'] == bk_id] if not df_costs.empty and 'Booking ID' in df_costs.columns else pd.DataFrame()
                
                items_list = []
                if not job_sales.empty:
                    for idx, row in job_sales.reset_index().iterrows():
                        if safe_float(row.get('Selling Price', 0.0)) <= 0:
                            continue
                        is_reimb = False
                        if 'Reimbursement' in row and row['Reimbursement'] is not None:
                            is_reimb = bool(row['Reimbursement'])
                        else:
                            charge_lower = safe_str(row.get('Charge Item')).lower()
                            if 'reimbursement' in charge_lower or 'จ่ายแทน' in charge_lower:
                                is_reimb = True
                        
                        items_list.append({
                            "Charge Item": safe_str(row.get('Charge Item')),
                            "Container Type": safe_str(row.get('Container Type')),
                            "Quantity": safe_float(row.get('Quantity', 1.0)),
                            "Unit Price": safe_float(row.get('Selling Price', 0.0)),
                            "Currency": safe_str(row.get('Selling Currency', 'THB')),
                            "Exchange Rate": safe_float(row.get('Selling Exchange Rate', 1.0)),
                            "VAT Rate (%)": 0.0 if is_reimb else 7.0,
                            "Tax Rate (%)": 0.0 if is_reimb else 1.0,
                            "Reimbursement": is_reimb
                        })
                    items_list.sort(key=get_item_sort_key)
                    st.session_state['invoice_items_edit'] = items_list
                    st.toast("โหลดราคาขายจาก Job Costing ล่าสุดเรียบร้อยแล้ว!")
                else:
                    st.warning("ไม่พบข้อมูลราคาขายสำหรับ Booking นี้ในระบบ Job Costing")
            st.session_state['prev_reload_costing_edit'] = reload_costing

            # ลอจิกการลบใบแจ้งหนี้ทิ้ง
            if delete_btn:
                try:
                    df_ind_all_current = get_data_from_sheet('Invoice_Detail')
                    existing_details = df_ind_all_current[df_ind_all_current['Invoice ID'] == sel_inv_id] if not df_ind_all_current.empty else pd.DataFrame()
                    if not existing_details.empty:
                        delete_records_bulk('Invoice_Detail', existing_details['Invoice Detail ID'].tolist())
                    delete_records_bulk('Invoice_Header', [sel_inv_id])
                    st.success(f"🗑️ ลบใบแจ้งหนี้ {sel_inv_id} สำเร็จเรียบร้อยแล้ว!")
                    st.session_state['invoice_items_edit'] = None
                    st.session_state['prev_sel_inv_id'] = None
                    st.session_state['reload_costing_checkbox_edit'] = False
                    st.session_state['prev_reload_costing_edit'] = False
                    st.rerun()
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดในการลบใบแจ้งหนี้: {e}")

            st.markdown("---")
            st.markdown("### 📝 รายการเรียกเก็บเงิน")
            invoice_items_edit = st.session_state.get('invoice_items_edit', [])
            
            if not invoice_items_edit:
                st.warning("❌ ไม่พบรายการเรียกเก็บเงินสำหรับใบแจ้งหนี้นี้")
            else:
                h_cols = st.columns([2.0, 1.0, 0.6, 1.2, 1.0, 0.8, 0.9, 0.9, 1.4])
                h_cols[0].markdown("**รายการ**")
                h_cols[1].markdown("**ชนิดตู้**")
                h_cols[2].markdown("**QTY**")
                h_cols[3].markdown("**ราคา**")
                h_cols[4].markdown("**เรทเงิน**")
                h_cols[5].markdown("**จ่ายแทน**")
                h_cols[6].markdown("**VAT %**")
                h_cols[7].markdown("**WHT %**")
                h_cols[8].markdown("**รวม (THB)**")
                
                total_amt = 0.0
                reimb_amt = 0.0
                vat_amt = 0.0
                wht_amt = 0.0
                
                for idx, item in enumerate(invoice_items_edit):
                    r_cols = st.columns([2.0, 1.0, 0.6, 1.2, 1.0, 0.8, 0.9, 0.9, 1.4])
                    r_cols[0].text_input(f"รายการที่ {idx+1}", value=item["Charge Item"], disabled=True, key=f"inv_item_charge_edit_{idx}", label_visibility="collapsed")
                    r_cols[1].text_input(f"ชนิดตู้ {idx+1}", value=item["Container Type"], disabled=True, key=f"inv_item_ctype_edit_{idx}", label_visibility="collapsed")
                    
                    new_qty = r_cols[2].number_input(f"QTY {idx+1}", value=item["Quantity"], min_value=0.0, step=1.0, key=f"inv_item_qty_edit_{idx}", label_visibility="collapsed")
                    item["Quantity"] = new_qty
                    
                    new_price = r_cols[3].number_input(f"ราคา {idx+1} ({item['Currency']})", value=item["Unit Price"], min_value=0.0, step=10.0, key=f"inv_item_price_edit_{idx}", label_visibility="collapsed")
                    item["Unit Price"] = new_price
                    
                    new_ex = r_cols[4].number_input(f"เรทเงิน {idx+1}", value=item["Exchange Rate"], min_value=0.0, step=0.1, format="%.4f", key=f"inv_item_ex_edit_{idx}", label_visibility="collapsed")
                    item["Exchange Rate"] = new_ex
                    
                    new_reimb = r_cols[5].checkbox(f"จ่ายแทน {idx+1}", value=item["Reimbursement"], key=f"inv_item_reimb_edit_{idx}", label_visibility="collapsed")
                    item["Reimbursement"] = new_reimb
                    
                    vat_disabled = new_reimb
                    wht_disabled = new_reimb
                    
                    vat_opts = [0.0, 7.0]
                    if float(item["VAT Rate (%)"]) not in vat_opts:
                        vat_opts.append(float(item["VAT Rate (%)"]))
                    
                    vat_val = 0.0 if new_reimb else float(item["VAT Rate (%)"])
                    new_vat = r_cols[6].selectbox(f"VAT {idx+1}", vat_opts, index=vat_opts.index(vat_val), disabled=vat_disabled, key=f"inv_item_vat_edit_{idx}", label_visibility="collapsed")
                    item["VAT Rate (%)"] = new_vat
                    
                    wht_opts = [0.0, 1.0, 3.0, 5.0]
                    if float(item["Tax Rate (%)"]) not in wht_opts:
                        wht_opts.append(float(item["Tax Rate (%)"]))
                    
                    wht_val = 0.0 if new_reimb else float(item["Tax Rate (%)"])
                    new_wht = r_cols[7].selectbox(f"WHT {idx+1}", wht_opts, index=wht_opts.index(wht_val), disabled=wht_disabled, key=f"inv_item_wht_edit_{idx}", label_visibility="collapsed")
                    item["Tax Rate (%)"] = new_wht
                    
                    sub_total_thb = new_qty * new_price * new_ex
                    r_cols[8].text_input(f"รวม {idx+1}", value=f"{sub_total_thb:,.2f}", disabled=True, key=f"inv_item_total_edit_{idx}", label_visibility="collapsed")
                    
                    if item["Reimbursement"]:
                        reimb_amt += sub_total_thb
                    else:
                        total_amt += sub_total_thb
                        vat_amt += sub_total_thb * (new_vat / 100.0)
                        wht_amt += sub_total_thb * (new_wht / 100.0)

                st.markdown("---")
                total_amt = round_half_up(total_amt, 2)
                vat_amt = round_half_up(vat_amt, 2)
                wht_amt = round_half_up(wht_amt, 2)
                reimb_amt = round_half_up(reimb_amt, 2)
                grand_total = round_half_up(total_amt + vat_amt - wht_amt + reimb_amt, 2)
                
                col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
                col_m1.metric("มูลค่าบริการ", f"{total_amt:,.2f} THB")
                col_m2.metric("VAT", f"{vat_amt:,.2f} THB")
                col_m3.metric("WHT", f"{wht_amt:,.2f} THB")
                col_m4.metric("จ่ายแทน (Reimb.)", f"{reimb_amt:,.2f} THB")
                col_m5.metric("ยอดรวมชำระสุทธิ", f"{grand_total:,.2f} THB")
                
                st.markdown("---")
                
                # เตรียมปุ่ม PDF & บันทึกการแก้ไข
                col_save_1, col_save_2 = st.columns(2)
                with col_save_1:
                    bank_info = "KASIKORNBANK PUBLIC COMPANY MEGA BANGNA 2 BRANCH A/C NO. : 0321348335 (CURRENT ACCOUNT)" # ข้อมูลธนาคาร
                    
                    # ดึงข้อมูลที่อยู่และ Tax ID จากตาราง Customer โดยตรงตามผู้ใช้สั่ง
                    df_cust_table = get_data_from_sheet('Customer')
                    c_id = inv_row.get('Customer ID')
                    c_name = inv_row.get('Customer Name')
                    cust_address = ""
                    cust_tax = ""
                    if not df_cust_table.empty:
                        match = pd.DataFrame()
                        if c_id:
                            match = df_cust_table[df_cust_table['Customer ID'].astype(str) == safe_str(c_id)]
                        if match.empty and c_name:
                            match = df_cust_table[df_cust_table['Customer Name'].astype(str) == safe_str(c_name)]
                        if not match.empty:
                            cust_address = safe_str(match.iloc[0].get('Address'))
                            cust_tax = safe_str(match.iloc[0].get('Tax ID'))
                    
                    if not cust_address:
                        cust_address = inv_row.get('Customer Address', '')
                    if not cust_address and bk_row is not None:
                        cust_address = "กรุงเทพมหานคร ประเทศไทย"
                    
                    if not cust_tax:
                        cust_tax = inv_row.get('Customer Tax ID', '-')
                    
                    # พรีวิวข้อมูลที่จะแสดงใน PDF ตามค่าปัจจุบันที่แก้ไขบนหน้าจอ
                    preview_row = {
                        "Invoice ID": sel_inv_id,
                        "Invoice Date": fmt_date(st.session_state['inv_date_edit']),
                        "Due Date": fmt_date(st.session_state['due_date_edit']),
                        "Booking ID": bk_id,
                        "Customer ID": inv_row.get('Customer ID', ''),
                        "Customer Name": inv_row.get('Customer Name', ''),
                        "Total Amount": total_amt,
                        "VAT Amount": vat_amt,
                        "WHT Amount": wht_amt,
                        "Reimbursement Amount": reimb_amt,
                        "Grand Total": grand_total,
                        "Status": inv_row.get('Status', 'ค้างชำระ')
                    }
                    
                    preview_details = pd.DataFrame([
                        {
                            "Invoice Detail ID": item.get("Invoice Detail ID", f"IND_PREV_{i}"),
                            "Invoice ID": sel_inv_id,
                            "Booking ID": bk_id,
                            "Charge Item": item["Charge Item"],
                            "Container Type": item["Container Type"],
                            "Quantity": item["Quantity"],
                            "Unit Price": item["Unit Price"],
                            "Currency": item["Currency"],
                            "Exchange Rate": item["Exchange Rate"],
                            "Amount": item["Quantity"] * item["Unit Price"] * item["Exchange Rate"],
                            "VAT Rate (%)": item["VAT Rate (%)"],
                            "Tax Rate (%)": item["Tax Rate (%)"],
                            "Reimbursement": item["Reimbursement"]
                        } for i, item in enumerate(invoice_items_edit)
                    ])
                    
                    pdf_data = create_invoice_pdf(preview_row, preview_details, bk_row, bank_info, cust_address, get_data_from_sheet('Booking_Detail'), cust_tax)
                    st.download_button(
                        label="📄 พิมพ์ใบแจ้งหนี้ (PDF)",
                        data=pdf_data,
                        file_name=f"{sel_inv_id}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"download_invoice_pdf_edit_{sel_inv_id}"
                    )
                with col_save_2:
                    save_btn = st.button("💾 บันทึกการแก้ไขใบแจ้งหนี้", type="primary", use_container_width=True, key="save_invoice_edit_btn")
                    
                if save_btn:
                    try:
                        # 1. อัปเดตข้อมูลหลัก (Header)
                        header_update = {
                            "Invoice Date": fmt_date(st.session_state['inv_date_edit']),
                            "Due Date": fmt_date(st.session_state['due_date_edit']),
                            "Total Amount": total_amt,
                            "VAT Amount": vat_amt,
                            "WHT Amount": wht_amt,
                            "Reimbursement Amount": reimb_amt,
                            "Grand Total": grand_total
                        }
                        update_record('Invoice_Header', sel_inv_id, header_update)
                        
                        # 2. ลบรายละเอียดใบแจ้งหนี้เดิมทั้งหมด
                        df_ind_all_current = get_data_from_sheet('Invoice_Detail')
                        existing_details = df_ind_all_current[df_ind_all_current['Invoice ID'] == sel_inv_id] if not df_ind_all_current.empty else pd.DataFrame()
                        if not existing_details.empty:
                            delete_records_bulk('Invoice_Detail', existing_details['Invoice Detail ID'].tolist())
                            
                        # 3. เพิ่มรายละเอียดใบแจ้งหนี้ใหม่ที่แก้ไขแล้วเข้าไปใหม่
                        max_ind_num = 0
                        df_ind = get_data_from_sheet('Invoice_Detail')
                        if not df_ind.empty and 'Invoice Detail ID' in df_ind.columns:
                            for val in df_ind['Invoice Detail ID'].dropna():
                                v_str = safe_str(val)
                                if v_str.startswith('IND'):
                                    try:
                                        num = int(v_str.replace('IND', ''))
                                        if num > max_ind_num: max_ind_num = num
                                    except: pass
                                    
                        inv_details = []
                        for i, item in enumerate(invoice_items_edit):
                            sub_total_thb = item["Quantity"] * item["Unit Price"] * item["Exchange Rate"]
                            new_ind_id = f"IND{(max_ind_num + 1 + i):04d}"
                            inv_details.append({
                                "Invoice Detail ID": new_ind_id,
                                "Invoice ID": sel_inv_id,
                                "Booking ID": bk_id,
                                "Charge Item": item["Charge Item"],
                                "Container Type": item["Container Type"],
                                "Quantity": item["Quantity"],
                                "Unit Price": item["Unit Price"],
                                "Currency": item["Currency"],
                                "Exchange Rate": item["Exchange Rate"],
                                "Amount": sub_total_thb,
                                "VAT Rate (%)": item["VAT Rate (%)"],
                                "Tax Rate (%)": item["Tax Rate (%)"],
                                "Reimbursement": item["Reimbursement"]
                            })
                        append_records_bulk('Invoice_Detail', inv_details)
                        
                        st.success(f"🎉 แก้ไขใบแจ้งหนี้ {sel_inv_id} สำเร็จเรียบร้อยแล้ว!")
                        st.session_state['invoice_items_edit'] = None
                        st.session_state['prev_sel_inv_id'] = None
                        st.session_state['reload_costing_checkbox_edit'] = False
                        st.session_state['prev_reload_costing_edit'] = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาดในการบันทึกการแก้ไขใบแจ้งหนี้: {e}")

# --- Page 4: รับชำระเงิน (Receipt) ---
elif page == "💰 รับชำระเงิน (Receipt)":
    st.header("ระบบออกใบเสร็จรับเงิน (Receipt)")
    rec_tab1, rec_tab2 = st.tabs(["💰 ออกใบเสร็จรับเงินใหม่", "🔍 ค้นหา/พิมพ์ ใบเสร็จ"])
    
    with rec_tab1:
        df_inv_all = get_data_from_sheet('Invoice_Header')
        df_rec_all_check = get_data_from_sheet('Receipt_Header')
        existing_rec_inv_ids = set(df_rec_all_check['Invoice ID'].dropna().unique()) if not df_rec_all_check.empty else set()
        unpaid_invs = pd.DataFrame()
        if not df_inv_all.empty:
            unpaid_invs = df_inv_all[df_inv_all['Status'].isin(['ค้างชำระ', 'Pending', 'Unpaid', 'รอชำระ']) | (~df_inv_all['Invoice ID'].isin(existing_rec_inv_ids))]
            unpaid_invs = unpaid_invs.sort_values(by='Invoice ID', ascending=False)
            
        if unpaid_invs.empty:
            st.info("ไม่มีใบแจ้งหนี้ค้างชำระสำหรับการออกใบเสร็จ")
        else:
            # Create mapping from booking ID to booking number and B/L number
            bk_id_to_num = {}
            bk_id_to_bl = {}
            if not df_bk_all_global.empty and 'Booking ID' in df_bk_all_global.columns:
                for _, bk_r in df_bk_all_global.iterrows():
                    b_id = safe_str(bk_r.get('Booking ID'))
                    b_num = safe_str(bk_r.get('Booking Number'))
                    b_bl = safe_str(bk_r.get('B/L Number'))
                    if b_id:
                        bk_id_to_num[b_id] = b_num
                        bk_id_to_bl[b_id] = b_bl
            
            inv_opts_rec = []
            for idx, r in unpaid_invs.iterrows():
                inv_id_val = safe_str(r['Invoice ID'])
                bk_id_val = safe_str(r.get('Booking ID'))
                bk_num_val = bk_id_to_num.get(bk_id_val, '-') if bk_id_val else '-'
                bl_num_val = bk_id_to_bl.get(bk_id_val, '-') if bk_id_val else '-'
                cust_name_val = safe_str(r.get('Customer Name'))
                inv_opts_rec.append(f"{inv_id_val} | BKG ID: {bk_id_val if bk_id_val else '-'} | Booking No: {bk_num_val} | B/L: {bl_num_val} | ลูกค้า: {cust_name_val}")
                
            sel_inv_rec = st.selectbox("เลือกใบแจ้งหนี้เพื่อบันทึกจ่ายเงิน:", inv_opts_rec)
            sel_inv_id = sel_inv_rec.split(" | ")[0].strip()
            
            inv_row = df_inv_all[df_inv_all['Invoice ID'] == sel_inv_id].iloc[0]
            
            # รายละเอียดการรับชำระเงิน
            with st.form("create_receipt_form"):
                rec_date = st.date_input("Receipt Date", value=datetime.date.today())
                pay_method = st.selectbox("Payment Method (วิธีรับชำระ)", ["เงินโอนเข้าบัญชีธนาคาร (Bank Transfer)", "เงินสด (Cash)", "เช็คสั่งจ่าย (Cheque)"])
                pay_ref = st.text_input("Payment Reference (เลขสลิปโอนเงิน / เลขเช็ค)")
                
                if st.form_submit_button("💾 ยืนยันการชำระเงินและออกใบเสร็จ"):
                    try:
                        new_rec_id = generate_next_year_id('Receipt_Header', 'Receipt ID', 'REC')
                        
                        rec_record = {
                            "Receipt ID": new_rec_id,
                            "Receipt Date": fmt_date(rec_date),
                            "Invoice ID": sel_inv_id,
                            "Customer Name": inv_row.get('Customer Name'),
                            "Customer Address": inv_row.get('Customer Address', 'กรุงเทพมหานคร'),
                            "Customer Tax ID": inv_row.get('Customer Tax ID', '-'),
                            "Payment Method": pay_method,
                            "Payment Ref": pay_ref,
                            "Grand Total": inv_row.get('Grand Total')
                        }
                        
                        # บันทึกใบเสร็จ
                        append_record('Receipt_Header', rec_record)
                        
                        # อัปเดตสถานะใบแจ้งหนี้เป็น "ชำระเงินแล้ว"
                        update_record('Invoice_Header', inv_row['Invoice ID'], {"Status": "ชำระเงินแล้ว"})
                        
                        st.success(f"🎉 ออกใบเสร็จรหัส {new_rec_id} เรียบร้อย และเปลี่ยนสถานะใบแจ้งหนี้เป็น ชำระเงินแล้ว!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาดในการบันทึกใบเสร็จ: {e}")

    with rec_tab2:
        df_rec_all = get_data_from_sheet('Receipt_Header')
        if df_rec_all.empty:
            st.info("ยังไม่มีประวัติการออกใบเสร็จในระบบ")
        else:
            df_inv_all = get_data_from_sheet('Invoice_Header')
            df_bk_all = get_data_from_sheet('Booking_Header')
            
            rec_opts = []
            for _, r in df_rec_all.iterrows():
                rec_id = r['Receipt ID']
                cust_name = r.get('Customer Name', '-')
                inv_id = r.get('Invoice ID')
                bk_no = "N/A"
                if not df_inv_all.empty and inv_id in df_inv_all['Invoice ID'].values:
                    inv_match = df_inv_all[df_inv_all['Invoice ID'] == inv_id]
                    if not inv_match.empty:
                        bk_id = inv_match.iloc[0].get('Booking ID')
                        if not df_bk_all.empty and bk_id in df_bk_all['Booking ID'].values:
                            bk_match = df_bk_all[df_bk_all['Booking ID'] == bk_id]
                            if not bk_match.empty:
                                bk_no = str(bk_match.iloc[0].get('Booking Number', 'N/A'))
                rec_opts.append(f"{rec_id} - {cust_name} (BK: {bk_no})")
                
            sel_rec_opt = st.selectbox("เลือกใบเสร็จที่ต้องการดู:", rec_opts)
            sel_rec_id = sel_rec_opt.split(" - ")[0]
            
            rec_row = df_rec_all[df_rec_all['Receipt ID'] == sel_rec_id].iloc[0]
            
            # ดึงข้อมูล Invoice และ Booking ที่เกี่ยวข้อง
            inv_id = rec_row.get('Invoice ID')
            df_inv_all = get_data_from_sheet('Invoice_Header')
            inv_row = df_inv_all[df_inv_all['Invoice ID'] == inv_id].iloc[0] if not df_inv_all.empty and inv_id in df_inv_all['Invoice ID'].values else None
            
            df_ind_all = get_data_from_sheet('Invoice_Detail')
            inv_dtl = df_ind_all[df_ind_all['Invoice ID'] == inv_id] if not df_ind_all.empty and inv_id in df_ind_all['Invoice ID'].values else pd.DataFrame()
            
            bk_id = inv_row.get('Booking ID') if inv_row is not None else None
            df_bk_all = get_data_from_sheet('Booking_Header')
            bk_row = df_bk_all[df_bk_all['Booking ID'] == bk_id].iloc[0] if not df_bk_all.empty and bk_id in df_bk_all['Booking ID'].values else None
            
            st.write("---")
            st.markdown(f"### ใบเสร็จรับเงิน/ใบกำกับภาษี: {sel_rec_id}")
            st.markdown(f"🗓️ วันที่ชำระ: {rec_row.get('Receipt Date')} | ยอดชำระ: {rec_row.get('Grand Total'):,.2f} THB | อ้างอิง: **{rec_row.get('Payment Ref')}**")
            
            if not inv_dtl.empty:
                inv_dtl_display = inv_dtl[inv_dtl.apply(lambda r: safe_float(r.get('Unit Price'), 0) > 0 or safe_float(r.get('Amount'), 0) > 0, axis=1)].copy()
                inv_dtl_display['sort_key'] = inv_dtl_display.apply(lambda r: get_item_sort_key(r.to_dict()), axis=1)
                inv_dtl_display = inv_dtl_display.sort_values(by='sort_key').drop(columns=['sort_key'])
            else:
                inv_dtl_display = inv_dtl
            st.dataframe(inv_dtl_display[['Charge Item', 'Container Type', 'Quantity', 'Amount']], use_container_width=True)
            
            c1, c2, c3 = st.columns(3)
            with c1:
                # พิมพ์ตัวจริง
                pdf_data_real = create_receipt_pdf(rec_row, inv_row, inv_dtl, bk_row, is_copy=False)
                st.download_button(
                    label="📄 ดาวน์โหลดใบเสร็จ (ตัวจริง) PDF",
                    data=pdf_data_real,
                    file_name=f"{sel_rec_id}_Original.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"dl_receipt_orig_{sel_rec_id}"
                )
            with c2:
                # พิมพ์สำเนา
                pdf_data_copy = create_receipt_pdf(rec_row, inv_row, inv_dtl, bk_row, is_copy=True)
                st.download_button(
                    label="📄 ดาวน์โหลดใบเสร็จ (สำเนา) PDF",
                    data=pdf_data_copy,
                    file_name=f"{sel_rec_id}_Copy.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"dl_receipt_copy_{sel_rec_id}"
                )
            with c3:
                delete_rec_btn = st.button("🗑️ ลบใบเสร็จ", type="primary", use_container_width=True, key=f"delete_receipt_btn_{sel_rec_id}")
                if delete_rec_btn:
                    try:
                        # 1. ปรับสถานะใบแจ้งหนี้กลับเป็น ค้างชำระ
                        if inv_row is not None and inv_id:
                            update_record('Invoice_Header', inv_id, {"Status": "ค้างชำระ"})
                        # 2. ลบใบเสร็จ
                        delete_records_bulk('Receipt_Header', [sel_rec_id])
                        st.success(f"🗑️ ลบใบเสร็จ {sel_rec_id} เรียบร้อยแล้ว!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาดในการลบใบเสร็จ: {e}")

# --- Page 5: รายงาน (Reports) ---
elif page == "📊 รายงาน (Reports)":
    st.header("📊 รายงานและสถิติภาพรวมธุรกิจ (Business Analytics & Reports)")
    
    df_bk = get_data_from_sheet('Booking_Header')
    df_inv = get_data_from_sheet('Invoice_Header')
    df_costing = get_data_from_sheet('Job_Costing')
    df_cust = get_data_from_sheet('Customer')
    df_liner = get_data_from_sheet('Liner')
    df_bd = get_data_from_sheet('Booking_Detail')
    
    if df_bk.empty:
        st.info("ยังไม่มีข้อมูลสำหรับประมวลผลรายงาน")
    else:
        # --- ส่วนที่ 1: เลือกช่วงวันที่ (Date Range Filter) ---
        st.subheader("📅 ตัวกรองรายงาน (Report Filter)")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            start_date = st.date_input("ตั้งแต่วันที่ (Start Date)", value=datetime.date.today().replace(day=1), format="DD/MM/YYYY")
        with col_f2:
            end_date = st.date_input("ถึงวันที่ (End Date)", value=datetime.date.today(), format="DD/MM/YYYY")
            
        # กรอง df_bk ตามช่วงวันที่
        def parse_bk_date(val):
            d = p_date(val)
            return d if d else datetime.date(1970, 1, 1)
            
        df_bk['Parsed Date'] = df_bk['Booking Date'].apply(parse_bk_date)
        filtered_bk = df_bk[(df_bk['Parsed Date'] >= start_date) & (df_bk['Parsed Date'] <= end_date)].copy()
        
        if filtered_bk.empty:
            st.warning("⚠️ ไม่พบข้อมูล Booking ในช่วงวันที่เลือก")
        else:
            # คำนวณสถิติภาพรวม
            total_jobs = len(filtered_bk)
            
            # คำนวณกำไร/รายได้จาก Job_Costing สำหรับ Job ที่กรองมา
            bk_ids = set(filtered_bk['Booking ID'].astype(str))
            
            total_cost_all = 0.0
            total_sell_all = 0.0
            total_profit_all = 0.0
            
            cost_map = {}
            sell_map = {}
            profit_map = {}
            
            if not df_costing.empty and 'Booking ID' in df_costing.columns:
                df_costing['Total Cost (THB)'] = df_costing.apply(lambda r: safe_float(r.get('Cost Price')) * safe_float(r.get('Cost Exchange Rate', 1.0)) * safe_float(r.get('Quantity', 1.0)), axis=1)
                df_costing['Total Selling (THB)'] = df_costing.apply(lambda r: safe_float(r.get('Selling Price')) * safe_float(r.get('Selling Exchange Rate', 1.0)) * safe_float(r.get('Quantity', 1.0)), axis=1)
                df_costing['Profit (THB)'] = df_costing['Total Selling (THB)'] - df_costing['Total Cost (THB)']
                
                for b_id, group in df_costing.groupby('Booking ID'):
                    b_str = safe_str(b_id)
                    c_sum = group['Total Cost (THB)'].sum()
                    s_sum = group['Total Selling (THB)'].sum()
                    p_sum = group['Profit (THB)'].sum()
                    cost_map[b_str] = c_sum
                    sell_map[b_str] = s_sum
                    profit_map[b_str] = p_sum
                    if b_str in bk_ids:
                        total_cost_all += c_sum
                        total_sell_all += s_sum
                        total_profit_all += p_sum
                        
            # แสดง Metric ภาพรวม
            c1, c2, c3 = st.columns(3)
            c1.metric("📌 จำนวนงานในช่วงวันที่เลือก", f"{total_jobs} รายการ")
            c2.metric("💰 ยอดขายรวม (Total Selling)", f"{total_sell_all:,.2f} THB")
            c3.metric("📈 กำไรสุทธิรวม (Net Profit)", f"{total_profit_all:,.2f} THB", delta=f"{(total_profit_all / total_sell_all * 100 if total_sell_all > 0 else 0):.1f}% Margin")
            
            st.markdown("---")
            
            # --- ส่วนที่ 2: กราฟวิเคราะห์ (Charts & Analytics) ---
            # แมป Customer Short Name
            cust_short_map = {}
            if not df_cust.empty and 'Customer Name' in df_cust.columns and 'Customer Short Name' in df_cust.columns:
                for _, r in df_cust.iterrows():
                    c_name = safe_str(r.get('Customer Name'))
                    c_short = safe_str(r.get('Customer Short Name'))
                    if c_name:
                        cust_short_map[c_name] = c_short if c_short else c_name
                        
            # แมป Liner Short Name
            liner_short_map = {}
            if not df_liner.empty and 'Liner Name' in df_liner.columns:
                for _, r in df_liner.iterrows():
                    l_name = safe_str(r.get('Liner Name'))
                    l_short = safe_str(r.get('Liner Short Name', l_name))
                    if l_name:
                        liner_short_map[l_name] = l_short if l_short else l_name
                        
            # แมป Volume จาก Booking_Detail
            vol_map = {}
            if not df_bd.empty and 'Booking ID' in df_bd.columns:
                for b_id, group in df_bd.groupby('Booking ID'):
                    v_list = []
                    for _, r in group.iterrows():
                        num_val = safe_float(r.get('Number'), 0)
                        if num_val > 0:
                            v_list.append(f"{num_val:g} x {safe_str(r.get('Container Type'))}")
                        else:
                            v_list.append(safe_str(r.get('Container Type')))
                    vol_map[safe_str(b_id)] = ", ".join([v for v in v_list if v])
                    
            # สร้างตารางข้อมูล 14 คอลัมน์
            report_rows = []
            for _, r in filtered_bk.iterrows():
                b_id = safe_str(r.get('Booking ID'))
                c_full = safe_str(r.get('Customer'))
                c_short = cust_short_map.get(c_full, c_full)
                l_full = safe_str(r.get('Liner'))
                l_short = liner_short_map.get(l_full, l_full)
                
                vol_str = vol_map.get(b_id, "")
                if not vol_str:
                    w = safe_float(r.get('Weight'), 0)
                    m = safe_float(r.get('Measurement'), 0)
                    if w > 0 or m > 0:
                        vol_str = f"LCL ({w:g} KGS / {m:g} CBM)"
                    else:
                        vol_str = "-"
                        
                c_val = cost_map.get(b_id, 0.0)
                s_val = sell_map.get(b_id, 0.0)
                p_val = profit_map.get(b_id, 0.0)
                
                report_rows.append({
                    "booking id": b_id,
                    "booking date": safe_str(r.get('Booking Date')),
                    "customer (short name)": c_short,
                    "booking number": safe_str(r.get('Booking Number')),
                    "b/l number": safe_str(r.get('B/L Number')),
                    "volume": vol_str,
                    "port loading": safe_str(r.get('Port Loading')),
                    "port discharge": safe_str(r.get('Port Discharge')),
                    "liner (short name)": l_short,
                    "etd": safe_str(r.get('ETD')),
                    "eta": safe_str(r.get('ETA')),
                    "cost (thb)": c_val,
                    "selling (thb)": s_val,
                    "profit (thb)": p_val
                })
                
            df_report = pd.DataFrame(report_rows)
            
            # กราฟ
            col_ch1, col_ch2 = st.columns(2)
            with col_ch1:
                st.markdown("#### 🏆 กำไรสุทธิแยกตามลูกค้า (Net Profit by Customer)")
                cust_profit = df_report.groupby('customer (short name)')['profit (thb)'].sum().reset_index()
                cust_profit = cust_profit.sort_values(by='profit (thb)', ascending=False)
                st.bar_chart(data=cust_profit, x='customer (short name)', y='profit (thb)', use_container_width=True)
                
            with col_ch2:
                st.markdown("#### 🚢 สัดส่วนการใช้สายเรือ (Liner Usage Distribution)")
                liner_dist = df_report['liner (short name)'].value_counts().reset_index()
                liner_dist.columns = ['liner', 'count']
                if not liner_dist.empty:
                    donut = alt.Chart(liner_dist).mark_arc(innerRadius=50).encode(
                        theta=alt.Theta(field="count", type="quantitative"),
                        color=alt.Color(field="liner", type="nominal", title="สายเรือ"),
                        tooltip=['liner', 'count']
                    ).properties(height=300)
                    st.altair_chart(donut, use_container_width=True)
                else:
                    st.info("ไม่มีข้อมูลสายเรือ")
                    
            st.markdown("---")
            
            # --- ส่วนที่ 3: ตารางข้อมูลรายงาน & ดาวน์โหลด Excel ---
            st.markdown("#### 📋 ตารางข้อมูลสรุปการขนส่งและกำไร (Shipment & Profit Report Table)")
            
            # จัดรูปแบบตัวเลขสำหรับการแสดงผลบนตารางเว็บ
            df_display = df_report.copy()
            df_display['cost (thb)'] = df_display['cost (thb)'].apply(lambda x: f"{x:,.2f}")
            df_display['selling (thb)'] = df_display['selling (thb)'].apply(lambda x: f"{x:,.2f}")
            df_display['profit (thb)'] = df_display['profit (thb)'].apply(lambda x: f"{x:,.2f}")
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            # ปุ่มดาวน์โหลด Excel (.xlsx)
            def generate_excel_report(df):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Shipment_Report')
                return output.getvalue()
                
            excel_bytes = generate_excel_report(df_report)
            
            st.download_button(
                label="📥 ดาวน์โหลดรายงานเป็นไฟล์ Excel (.xlsx)",
                data=excel_bytes,
                file_name=f"ROCCO_Report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
