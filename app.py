import streamlit as st
import pdfplumber
import re
import pandas as pd

st.set_page_config(page_title="PDF Invoice Extractor", layout="wide")

st.title("📄 PDF Invoice Extractor Tool")

uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

# ---------- TEXT EXTRACTION ----------
def extract_text(pdf_file):
    text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

# ---------- HELPERS ----------
def get_value(pattern, text):
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""

# ---------- TRADING ----------
def extract_trading(text):
    blocks = text.split("Material#:")
    results = []

    for b in blocks[1:]:
        data = {
            "Invoice Number": get_value(r'Invoice Number:\s*(\d+)', b),
            "Reference Invoice #": get_value(r'Reference Invoice #:\s*(\S+)', b),
            "Material#": get_value(r'^(\S+)', b),
            "PO#": get_value(r'PO#:\s*(\d+)', b),
            "PO Line Item Seq.#": get_value(r'PO Line Item Seq.#:\s*(\d+)', b),
            "Total Cartons": get_value(r'Total Number of Cartons:\s*(\d+)', b),
            "Total Quantity": get_value(r'Total Invoice Quantity:\s*([\d,]+)', b),
            "Total Amount": get_value(r'Total Amount:\s*([\d,.]+)', b),
            "Gross Weight": get_value(r'Total Gross Weight\s*:\s*([\d.]+)', b),
        }
        results.append(data)
    return pd.DataFrame(results)

# ---------- FACTORY ----------
def extract_factory(text):
    blocks = text.split("Factory Commercial Invoice")
    results = []

    for b in blocks[1:]:
        data = {
            "Invoice Number": get_value(r'Invoice Number:\s*(\d+)', b),
            "Reference Invoice #": get_value(r'Reference Invoice #:\s*(\S+)', b),
            "Material #": get_value(r'Material #:\s*(\S+)', b),
            "PO#": get_value(r'PO#:\s*(\d+)', b),
            "PO Line Item Seq. #": get_value(r'PO Line Item Seq. #:\s*(\d+)', b),
            "Total Cartons": get_value(r'Total Number of Cartons:\s*(\d+)', b),
            "Total Quantity": get_value(r'Total Invoice Quantity:\s*([\d,]+)', b),
            "Total Amount": get_value(r'Total Amount:\s*([\d,.]+)', b),
            "Gross Weight": get_value(r'Total Gross Weight:\s*([\d.]+)', b),
        }
        results.append(data)
    return pd.DataFrame(results)

# ---------- PACKING ----------
def extract_packing(text):
    blocks = text.split("Factory Packing List")
    results = []

    for b in blocks[1:]:
        data = {
            "Invoice Number": get_value(r'Invoice Number\.:\s*(.+)', b),
            "Material": get_value(r'Material:\s*(\S+)', b),
            "Reference PO#": get_value(r'Reference PO#:\s*(\d+)', b),
            "Item Seq.": get_value(r'Item Seq\.:\s*(\d+)', b),
            "Total Cartons": get_value(r'Total Cartons:\s*(\d+)', b),
            "Total Units": get_value(r'Total Units:\s*(\d+)', b),
            "Total Gross Kgs": get_value(r'Total Gross Kgs:\s*([\d.]+)', b),
            "Total CBM": get_value(r'Total CBM:\s*([\d.]+)', b),
        }
        results.append(data)
    return pd.DataFrame(results)

# ---------- MAIN ----------
if uploaded_file:
    text = extract_text(uploaded_file)

    st.success("PDF loaded successfully!")

    trading_df = extract_trading(text)
    factory_df = extract_factory(text)
    packing_df = extract_packing(text)

    st.subheader("Trading Company Commercial Invoice")
    st.dataframe(trading_df)

    st.subheader("Factory Commercial Invoice")
    st.dataframe(factory_df)

    st.subheader("Factory Packing List")
    st.dataframe(packing_df)

    # Export to Excel
    def to_excel():
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
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
