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

# ---------- HELPERS ----------
def get_value(pattern, text):
    match = re.search(pattern, text, re.S)
    return match.group(1).strip() if match else ""

# ---------- TRADING ----------
def extract_trading(pages):
    results = []

    for page_num, text in pages:

        invoice_no = get_value(r'Invoice Number\s*:\s*(\S+)', text)
        ref_invoice = get_value(r'Reference Invoice #\s*:\s*(\S+)', text)

        # ✅ FIX multiline
        total_cartons = get_value(
            r'Total\s*Number\s*of\s*Cartons[\s\n]*:?[\s\n]*([\d,]+)', text)

        total_quantity = get_value(
            r'Total\s*Invoice\s*Quantity[\s\n]*:?[\s\n]*([\d,]+)', text)

        total_amount = get_value(
            r'Total\s*Amount[\s\n]*:?[\s\n]*([\d,.]+)', text)

        gross_weight = get_value(
            r'Total\s*Gross\s*Weight[\s\n]*:?[\s\n]*([\d.]+)', text)

        blocks = text.split("Material#:")

        for b in blocks[1:]:

            data = {
                "Page": page_num,
                "Type": "Trading Company Commercial Invoice",
                "Invoice Number": invoice_no,
                "Reference Invoice #": ref_invoice,

                "Material#": get_value(
                    r'Material#\s*:\s*([A-Za-z0-9\-]+)',
                    "Material#:" + b
                ),

                "PO#": get_value(r'PO#\s*:\s*(\S+)', b),

                "PO Line Item Seq.#": get_value(
                    r'PO Line Item Seq\.?#\s*:\s*(\S+)', b),

                "Total Cartons": total_cartons,
                "Total Quantity": total_quantity,
                "Total Amount": total_amount,
                "Gross Weight": gross_weight,
            }

            results.append(data)

    return results

# ---------- FACTORY ----------
def extract_factory(pages):
    results = []

    for page_num, text in pages:
        blocks = text.split("Factory Commercial Invoice")

        for b in blocks[1:]:
            data = {
                "Page": page_num,
                "Type": "Factory Commercial Invoice",
                "Invoice Number": get_value(r'Invoice Number:\s*(\S+)', b),
                "Reference Invoice #": get_value(r'Reference Invoice #:\s*(\S+)', b),
                "Material #": get_value(r'Material #:\s*(\S+)', b),
                "PO#": get_value(r'PO#:\s*(\S+)', b),
                "PO Line Item Seq. #": get_value(r'PO Line Item Seq. #:\s*(\S+)', b),

                "Total Cartons": get_value(r'Total Number of Cartons[\s\n]*:?[\s\n]*([\d,]+)', b),
                "Total Quantity": get_value(r'Total Invoice Quantity[\s\n]*:?[\s\n]*([\d,]+)', b),
                "Total Amount": get_value(r'Total Amount[\s\n]*:?[\s\n]*([\d,.]+)', b),
                "Gross Weight": get_value(r'Total Gross Weight[\s\n]*:?[\s\n]*([\d.]+)', b),
            }
            results.append(data)

    return results

# ---------- PACKING ----------
def extract_packing(pages):
    results = []

    for page_num, text in pages:
        blocks = text.split("Factory Packing List")

        for b in blocks[1:]:

            invoice_raw = get_value(r'Invoice Number\.?\s*:\s*([^\n]+)', b)
            invoice_clean = re.split(r'AFS Category|Plant:|\s{2,}', invoice_raw)[0].strip()

            data = {
                "Page": page_num,
                "Type": "Factory Packing List",
                "Invoice Number": invoice_clean,

                "Material": get_value(r'Material:\s*(\S+)', b),
                "Reference PO#": get_value(r'Reference\s*PO#\s*:?\s*([A-Za-z0-9\-]+)', b),
                "Item Seq.": get_value(r'Item Seq[\s\.]*:?\s*([A-Za-z0-9]+)', b),

                "Total Cartons": get_value(r'Total Cartons[\s\n]*:?[\s\n]*([\d,]+)', b),
                "Total Units": get_value(r'Total Units[\s\n]*:?[\s\n]*([\d,]+)', b),
                "Total Gross Kgs": get_value(r'Total Gross Kgs[\s\n]*:?[\s\n]*([\d.]+)', b),
                "Total CBM": get_value(r'Total CBM[\s\n]*:?[\s\n]*([\d.]+)', b),
            }

            results.append(data)

    return results

# ---------- MERGE ----------
def merge_selected_columns(df):

    def coalesce(cols):
        cols = [c for c in cols if c in df.columns]
        if not cols:
            return ""
        return df[cols].bfill(axis=1).iloc[:, 0]

    if "Material#" in df.columns or "Material #" in df.columns:
        df["Material"] = coalesce(["Material#", "Material #"])
        df = df.drop(columns=[c for c in ["Material#", "Material #"] if c in df.columns])

    if "PO Line Item Seq.#" in df.columns or "PO Line Item Seq. #" in df.columns:
        df["PO Line Item Seq"] = coalesce(["PO Line Item Seq.#", "PO Line Item Seq. #"])
        df = df.drop(columns=[c for c in ["PO Line Item Seq.#", "PO Line Item Seq. #"] if c in df.columns])

    return df

# ---------- REMOVE EMPTY ROWS ----------
def remove_empty_rows(df):
    key_cols = ["Invoice Number", "Reference Invoice #"]
    other_cols = [c for c in df.columns if c not in key_cols]

    def is_empty_row(row):
        has_key = any(str(row.get(c, "")).strip() != "" for c in key_cols)
        others_empty = all(str(row.get(c, "")).strip() == "" for c in other_cols)
        return has_key and others_empty

    return df[~df.apply(is_empty_row, axis=1)]

# ---------- MAIN ----------
if uploaded_file:
    pages = extract_text_with_page(uploaded_file)

    trading = extract_trading(pages)
    factory = extract_factory(pages)
    packing = extract_packing(pages)

    df_all = pd.DataFrame(trading + factory + packing)

    df_all = merge_selected_columns(df_all)

    # ✅ REMOVE ROW RÁC
    df_all = remove_empty_rows(df_all)

    # SORT
    type_order = [
        "Trading Company Commercial Invoice",
        "Factory Commercial Invoice",
        "Factory Packing List",
    ]

    df_all["Type"] = pd.Categorical(df_all["Type"], categories=type_order, ordered=True)
    df_all = df_all.sort_values(by=["Page", "Type"])

    st.dataframe(df_all)

else:
    st.info("Please upload a PDF file")
