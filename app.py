import streamlit as st
import pdfplumber
import re
import pandas as pd

st.set_page_config(page_title="PDF Invoice Extractor", layout="wide")

st.title("📄 PDF Invoice Extractor Tool")

uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

# ---------- TEXT EXTRACTION WITH PAGE ----------
def extract_text_with_page(pdf_file):
    data = []
    with pdfplumber.open(pdf_file) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            data.append((i, text))
    return data

# ---------- HELPERS ----------
def get_value(pattern, text):
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""

# ---------- TRADING ----------
def extract_trading(pages):
    results = []

    for page_num, text in pages:
        blocks = text.split("Material#:")

        invoice_no = get_value(r'Invoice Number:\s*(\S+)', text)
        ref_invoice = get_value(r'Reference Invoice #:\s*(\S+)', text)

        for b in blocks[1:]:
            data = {
                "Page": page_num,
                "Type": "Trading Company Commercial Invoice",
                "Invoice Number": invoice_no,
                "Reference Invoice #": ref_invoice,
                "Material#": get_value(r'^(\S+)', b),
                "PO#": get_value(r'PO#:\s*(\S+)', b),
                "PO Line Item Seq.#": get_value(r'PO Line Item Seq.#:\s*(\S+)', b),
                "Total Cartons": get_value(r'Total Number of Cartons:\s*(\d+)', b),
                "Total Quantity": get_value(r'Total Invoice Quantity:\s*([\d,]+)', b),
                "Total Amount": get_value(r'Total Amount:\s*([\d,.]+)', b),
                "Gross Weight": get_value(r'Total Gross Weight\s*:\s*([\d.]+)', b),
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
                "Total Cartons": get_value(r'Total Number of Cartons:\s*(\d+)', b),
                "Total Quantity": get_value(r'Total Invoice Quantity:\s*([\d,]+)', b),
                "Total Amount": get_value(r'Total Amount:\s*([\d,.]+)', b),
                "Gross Weight": get_value(r'Total Gross Weight:\s*([\d.]+)', b),
            }
            results.append(data)
    return results

# ---------- PACKING ----------
def extract_packing(pages):
    results = []

    for page_num, text in pages:
        blocks = text.split("Factory Packing List")
        for b in blocks[1:]:
            invoice_raw = get_value(r'Invoice Number\\.:\\s*([^\\n]+)', b)
            invoice_clean = invoice_raw.split("AFS Category")[0].strip()

            data = {
                "Page": page_num,
                "Type": "Factory Packing List",
                "Invoice Number": invoice_clean,
                "Material": get_value(r'Material:\s*(\S+)', b),
                "Reference PO#": get_value(r'Reference PO#:\s*(\S+)', b),
                # FIX: flexible regex for Item Seq
                "Item Seq.": get_value(r'Item Seq\.?\s*:?\s*(\S+)', b),
                "Total Cartons": get_value(r'Total Cartons:\s*(\d+)', b),
                "Total Units": get_value(r'Total Units:\s*(\d+)', b),
                "Total Gross Kgs": get_value(r'Total Gross Kgs:\s*([\d.]+)', b),
                "Total CBM": get_value(r'Total CBM:\s*([\d.]+)', b),
            }
            results.append(data)
    return results

# ---------- MERGE SELECTED COLUMNS ----------
def merge_selected_columns(df):

    def coalesce(cols):
        cols = [c for c in cols if c in df.columns]
        if not cols:
            return ""
        return df[cols].bfill(axis=1).iloc[:, 0]

    # Merge Material
    if "Material#" in df.columns or "Material #" in df.columns:
        df["Material"] = coalesce(["Material#", "Material #"])
        df = df.drop(columns=[c for c in ["Material#", "Material #"] if c in df.columns])

    # Merge PO Line Item Seq
    if "PO Line Item Seq.#" in df.columns or "PO Line Item Seq. #" in df.columns:
        df["PO Line Item Seq"] = coalesce(["PO Line Item Seq.#", "PO Line Item Seq. #"])
        df = df.drop(columns=[c for c in ["PO Line Item Seq.#", "PO Line Item Seq. #"] if c in df.columns])

    return df

# ---------- MAIN ----------
if uploaded_file:
    pages = extract_text_with_page(uploaded_file)

    st.success("PDF loaded successfully!")

    trading = extract_trading(pages)
    factory = extract_factory(pages)
    packing = extract_packing(pages)

    all_data = trading + factory + packing
    df_all = pd.DataFrame(all_data)

    # APPLY MERGE HERE
    df_all = merge_selected_columns(df_all)

    # ---------- REORDER COLUMNS ----------
    def reorder_columns(df):
        cols = list(df.columns)

        def move_after(col_to_move, after_col):
            if col_to_move in cols and after_col in cols:
                cols.remove(col_to_move)
                idx = cols.index(after_col) + 1
                cols.insert(idx, col_to_move)

        # Move Material after Reference Invoice #
        move_after("Material", "Reference Invoice #")

        # Move PO Line Item Seq after PO#
        move_after("PO Line Item Seq", "PO#")

        return df[cols]

    df_all = reorder_columns(df_all)

    # ---------- SORT ----------
    type_order = [
        "Trading Company Commercial Invoice",
        "Factory Commercial Invoice",
        "Factory Packing List",
    ]

    df_all["Type"] = pd.Categorical(df_all["Type"], categories=type_order, ordered=True)
    df_all = df_all.sort_values(by=["Page", "Type"])

    # ---------- REMOVE BAD ROWS ----------
    cols_to_check = [
        c for c in df_all.columns
        if c not in ["Page", "Type", "Invoice Number", "Reference Invoice #"]
    ]

    mask_remove = (
        (df_all[cols_to_check].fillna("").eq("").all(axis=1))
        & (
            (df_all["Invoice Number"].fillna("") != "")
            | (df_all["Reference Invoice #"].fillna("") != "")
        )
    )

    df_all = df_all[~mask_remove]

    # ---------- DISPLAY ----------
    st.subheader("📊 All Data (Sorted by Page → Type)")
    st.dataframe(df_all)

    trading_df = df_all[df_all["Type"] == "Trading Company Commercial Invoice"]
    factory_df = df_all[df_all["Type"] == "Factory Commercial Invoice"]
    packing_df = df_all[df_all["Type"] == "Factory Packing List"]

    st.subheader("Trading Company Commercial Invoice")
    st.dataframe(trading_df)

    st.subheader("Factory Commercial Invoice")
    st.dataframe(factory_df)

    st.subheader("Factory Packing List")
    st.dataframe(packing_df)

    # ---------- EXPORT ----------
    def to_excel():
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_all.to_excel(writer, sheet_name='All_Data', index=False)
            trading_df.to_excel(writer, sheet_name='Trading', index=False)
            factory_df.to_excel(writer, sheet_name='Factory', index=False)
            packing_df.to_excel(writer, sheet_name='Packing', index=False)
        return output.getvalue()

    excel_data = to_excel()

    st.download_button(
        label="📥 Download Excel",
        data=excel_data,
        file_name="extracted_invoices.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Please upload a PDF file")
