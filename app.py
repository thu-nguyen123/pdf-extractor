import streamlit as st
import pdfplumber
import re
import pandas as pd

st.set_page_config(page_title="PDF Invoice Extractor", layout="wide")
st.title("📄 PDF Invoice Extractor Tool")

uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

# ---------- TEXT EXTRACTION ----------
def extract_text_with_page(pdf_file):
    data = []
    with pdfplumber.open(pdf_file) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            data.append((i, text))
    return data

# ---------- HELPER ----------
def get_value(pattern, text):
    try:
        text = re.sub(r'\s+', ' ', text)
        match = re.search(pattern, text, re.I)
        return match.group(1).strip() if match else ""
    except:
        return ""

# ---------- TRADING ----------
def extract_trading(pages):
    results = []

    for page_num, text in pages:
        if "Material#:" not in text:
            continue

        blocks = text.split("Material#:")

        invoice_no = get_value(r'Invoice Number\s*:\s*(\S+)', text)
        ref_invoice = get_value(r'Reference Invoice #\s*:\s*(\S+)', text)

        total_cartons = get_value(r'Total\s*Number\s*of\s*Cartons[\s:]*([\d,]+)', text)
        total_qty = get_value(r'Total\s*Invoice\s*Quantity[\s:]*([\d,]+)', text)
        total_amount = get_value(r'Total\s*Amount[\s:]*([\d,.\s]+)', text)
        gross_weight = get_value(r'Total\s*Gross\s*Weight[\s:]*([\d.\s]+)', text)

        for b in blocks[1:]:
            data = {
                "Page": page_num,
                "Type": "Trading Company Commercial Invoice",
                "Invoice Number": invoice_no,
                "Reference Invoice #": ref_invoice,
                "Material": get_value(r'^\s*([A-Za-z0-9\-]+)', b),
                "PO#": get_value(r'PO#\s*:\s*(\S+)', b),
                "PO Line Item Seq": get_value(r'PO Line Item Seq.*?:\s*(\S+)', b),
                "Total Cartons": total_cartons,
                "Total Quantity": total_qty,
                "Total Amount": total_amount,
                "Gross Weight": gross_weight,
            }
            results.append(data)

    return results

# ---------- FACTORY ----------
def extract_factory(pages):
    results = []

    for page_num, text in pages:
        if "Factory Commercial Invoice" not in text:
            continue

        blocks = text.split("Factory Commercial Invoice")

        for b in blocks[1:]:
            data = {
                "Page": page_num,
                "Type": "Factory Commercial Invoice",
                "Invoice Number": get_value(r'Invoice Number\s*:\s*(\S+)', b),
                "Reference Invoice #": get_value(r'Reference Invoice #\s*:\s*(\S+)', b),
                "Material": get_value(r'Material\s*#?\s*:\s*(\S+)', b),
                "PO#": get_value(r'PO#\s*:\s*(\S+)', b),
                "PO Line Item Seq": get_value(r'PO Line Item Seq.*?:\s*(\S+)', b),
                "Total Cartons": get_value(r'Total Number of Cartons[\s:]*([\d,]+)', b),
                "Total Quantity": get_value(r'Total Invoice Quantity[\s:]*([\d,]+)', b),
                "Total Amount": get_value(r'Total Amount[\s:]*([\d,.]+)', b),
                "Gross Weight": get_value(r'Total Gross Weight[\s:]*([\d.]+)', b),
            }
            results.append(data)

    return results

# ---------- PACKING ----------
def extract_packing(pages):
    results = []

    for page_num, text in pages:
        if "Factory Packing List" not in text:
            continue

        blocks = text.split("Factory Packing List")

        for b in blocks[1:]:
            invoice_raw = get_value(r'Invoice Number.*?:\s*([^\n]+)', b)
            invoice_clean = re.split(r'AFS Category|Plant:|\s{2,}', invoice_raw)[0].strip()

            data = {
                "Page": page_num,
                "Type": "Factory Packing List",
                "Invoice Number": invoice_clean,
                "Material": get_value(r'Material\s*:\s*(\S+)', b),
                "PO#": get_value(r'Reference\s*PO#\s*:?\s*(\S+)', b),
                "PO Line Item Seq": get_value(r'Item Seq.*?:\s*(\S+)', b),
                "Total Cartons": get_value(r'Total Cartons[\s:]*([\d,]+)', b),
                "Total Quantity": get_value(r'Total Units[\s:]*([\d,]+)', b),
                "Gross Weight": get_value(r'Total Gross Kgs[\s:]*([\d.]+)', b),
                "Total CBM": get_value(r'Total CBM[\s:]*([\d.]+)', b),
            }
            results.append(data)

    return results

# ---------- CLEAN ----------
def clean_dataframe(df):
    df = df.replace("", pd.NA)

    # ❗ XÓA HÀNG RỖNG (cái bạn cần)
    df = df.dropna(how="all")

    # ❗ XÓA HÀNG KHÔNG CÓ Material
    if "Material" in df.columns:
        df = df.dropna(subset=["Material"])

    return df

# ---------- MAIN ----------
if uploaded_file:
    try:
        pages = extract_text_with_page(uploaded_file)

        trading = extract_trading(pages)
        factory = extract_factory(pages)
        packing = extract_packing(pages)

        df_all = pd.DataFrame(trading + factory + packing)

        df_all = clean_dataframe(df_all)

        df_all = df_all.sort_values(by=["Page"])

        st.dataframe(df_all, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Lỗi: {e}")

else:
    st.info("Please upload a PDF file")
