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
    text = re.sub(r'\s+', ' ', text)
    match = re.search(pattern, text, re.I)
    return match.group(1).strip() if match else None  # 🔥 trả None để filter chuẩn

# ---------- TRADING ----------
def extract_trading(pages):
    results = []

    for page_num, text in pages:
        blocks = text.split("Material#:")

        invoice_no = get_value(r'Invoice Number\s*:\s*(\S+)', text)
        ref_invoice = get_value(r'Reference Invoice #\s*:\s*(\S+)', text)

        total_cartons = get_value(r'Total\s*Number\s*of\s*Cartons[\s:]*([\d,]+)', text)
        total_qty = get_value(r'Total\s*Invoice\s*Quantity[\s:]*([\d,]+)', text)
        total_amount = get_value(r'Total\s*Amount[\s:]*([\d,.\s]+)', text)
        gross_weight = get_value(r'Total\s*Gross\s*Weight[\s:]*([\d.\s]+)', text)

        for b in blocks[1:]:
            results.append({
                "Page": page_num,
                "Type": "Trading Company Commercial Invoice",
                "Invoice Number": invoice_no,
                "Reference Invoice #": ref_invoice,
                "Material#": get_value(r'^\s*([A-Za-z0-9\-]+)', b),
                "PO#": get_value(r'PO#\s*:\s*(\S+)', b),
                "PO Line Item Seq.#": get_value(r'PO Line Item Seq\.?#\s*:\s*(\S+)', b),
                "Total Cartons": total_cartons,
                "Total Quantity": total_qty,
                "Total Amount": total_amount,
                "Gross Weight": gross_weight,
            })

    return results

# ---------- FACTORY ----------
def extract_factory(pages):
    results = []

    for page_num, text in pages:
        blocks = text.split("Factory Commercial Invoice")

        for b in blocks[1:]:
            results.append({
                "Page": page_num,
                "Type": "Factory Commercial Invoice",
                "Invoice Number": get_value(r'Invoice Number\s*:\s*(\S+)', b),
                "Reference Invoice #": get_value(r'Reference Invoice #\s*:\s*(\S+)', b),
                "Material #": get_value(r'Material #\s*:\s*(\S+)', b),
                "PO#": get_value(r'PO#\s*:\s*(\S+)', b),
                "PO Line Item Seq. #": get_value(r'PO Line Item Seq\. #\s*:\s*(\S+)', b),
                "Total Cartons": get_value(r'Total Number of Cartons[\s:]*([\d,]+)', b),
                "Total Quantity": get_value(r'Total Invoice Quantity[\s:]*([\d,]+)', b),
                "Total Amount": get_value(r'Total Amount[\s:]*([\d,.]+)', b),
                "Gross Weight": get_value(r'Total Gross Weight[\s:]*([\d.]+)', b),
            })

    return results

# ---------- PACKING ----------
def extract_packing(pages):
    results = []

    for page_num, text in pages:
        blocks = text.split("Factory Packing List")

        for b in blocks[1:]:
            invoice_raw = get_value(r'Invoice Number\.?\s*:\s*([^\n]+)', b)
            invoice_clean = re.split(r'AFS Category|Plant:|\s{2,}', invoice_raw or "")[0].strip()

            results.append({
                "Page": page_num,
                "Type": "Factory Packing List",
                "Invoice Number": invoice_clean,
                "Material": get_value(r'Material\s*:\s*(\S+)', b),
                "Reference PO#": get_value(r'Reference\s*PO#\s*:?\s*([A-Za-z0-9\-]+)', b),
                "Item Seq.": get_value(r'Item Seq[\s\.]*:?\s*([A-Za-z0-9]+)', b),
                "Total Cartons": get_value(r'Total Cartons[\s:]*([\d,]+)', b),
                "Total Units": get_value(r'Total Units[\s:]*([\d,]+)', b),
                "Total Gross Kgs": get_value(r'Total Gross Kgs[\s:]*([\d.]+)', b),
                "Total CBM": get_value(r'Total CBM[\s:]*([\d.]+)', b),
            })

    return results

# ---------- MERGE ----------
def merge_selected_columns(df):

    def coalesce(cols):
        cols = [c for c in cols if c in df.columns]
        if not cols:
            return None
        return df[cols].bfill(axis=1).iloc[:, 0]

    if "Material#" in df.columns or "Material #" in df.columns:
        df["Material"] = coalesce(["Material#", "Material #"])
        df = df.drop(columns=[c for c in ["Material#", "Material #"] if c in df.columns])

    if "PO Line Item Seq.#" in df.columns or "PO Line Item Seq. #" in df.columns:
        df["PO Line Item Seq"] = coalesce(["PO Line Item Seq.#", "PO Line Item Seq. #"])
        df = df.drop(columns=[c for c in ["PO Line Item Seq.#", "PO Line Item Seq. #"] if c in df.columns])

    return df

# ---------- REORDER ----------
def reorder_columns(df):
    cols = list(df.columns)

    def move_after(col_to_move, after_col):
        if col_to_move in cols and after_col in cols:
            cols.remove(col_to_move)
            idx = cols.index(after_col) + 1
            cols.insert(idx, col_to_move)

    move_after("Material", "Reference Invoice #")
    move_after("PO Line Item Seq", "PO#")

    return df[cols]

# ---------- REMOVE INVALID ROWS ----------
def remove_invalid_rows(df):

    keep_rows = []

    for _, row in df.iterrows():
        invoice = row.get("Invoice Number")
        ref = row.get("Reference Invoice #")

        other_cols = row.drop(labels=["Invoice Number", "Reference Invoice #"], errors='ignore')

        # 🔥 nếu tất cả cột khác đều None hoặc rỗng → loại
        if pd.notna(invoice) or pd.notna(ref):
            if other_cols.notna().sum() == 0:
                continue

        keep_rows.append(row)

    return pd.DataFrame(keep_rows)

# ---------- MAIN ----------
try:
    if uploaded_file:

        pages = extract_text_with_page(uploaded_file)

        trading = extract_trading(pages)
        factory = extract_factory(pages)
        packing = extract_packing(pages)

        df_all = pd.DataFrame(trading + factory + packing)

        df_all = merge_selected_columns(df_all)
        df_all = reorder_columns(df_all)

        # 🔥 FIX CHÍNH Ở ĐÂY
        df_all = remove_invalid_rows(df_all)

        type_order = [
            "Trading Company Commercial Invoice",
            "Factory Commercial Invoice",
            "Factory Packing List",
        ]

        df_all["Type"] = pd.Categorical(df_all["Type"], categories=type_order, ordered=True)
        df_all = df_all.sort_values(by=["Page", "Type"])

        st.dataframe(df_all, use_container_width=True)

    else:
        st.info("Please upload a PDF file")

except Exception as e:
    st.error("❌ ERROR:")
    st.code(str(e))
