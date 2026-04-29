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
        blocks = text.split("Trading Company Commercial Invoice")
        for b in blocks[1:]:
            data = {
                "Page": page_num,
                "Type": "Trading Company Commercial Invoice",
                "Invoice Number": get_value(r'Invoice Number:\s*(\S+)', b),
                "Reference Invoice #": get_value(r'Reference Invoice #:\s*(\S+)', b),
                "Material#": get_value(r'Material#:\s*(\S+)', b),
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
            data = {
                "Page": page_num,
                "Type": "Factory Packing List",
                "Invoice Number": get_value(r'Invoice Number\.:\s*(.+)', b),
                "Material": get_value(r'Material:\s*(\S+)', b),
                "Reference PO#": get_value(r'Reference PO#:\s*(\S+)', b),
                "Item Seq.": get_value(r'Item Seq\.:\s*(\S+)', b),
                "Total Cartons": get_value(r'Total Cartons:\s*(\d+)', b),
                "Total Units": get_value(r'Total Units:\s*(\d+)', b),
                "Total Gross Kgs": get_value(r'Total Gross Kgs:\s*([\d.]+)', b),
                "Total CBM": get_value(r'Total CBM:\s*([\d.]+)', b),
            }
            results.append(data)
    return results

# ---------- MAIN ----------
if uploaded_file:

    with st.spinner("Đang xử lý PDF..."):
        pages = extract_text_with_page(uploaded_file)

        trading = extract_trading(pages)
        factory = extract_factory(pages)
        packing = extract_packing(pages)

        all_data = trading + factory + packing
        df_all = pd.DataFrame(all_data)

        # ---------- SORT LOGIC ----------
        type_order = [
            "Trading Company Commercial Invoice",
            "Factory Commercial Invoice",
            "Factory Packing List",
        ]

        df_all["Type"] = pd.Categorical(df_all["Type"], categories=type_order, ordered=True)
        df_all = df_all.sort_values(by=["Page", "Type"])

        st.success("✅ Extract thành công!")

        st.subheader("📊 All Data (Sorted)")
        st.dataframe(df_all)

        # Split sheet
        trading_df = df_all[df_all["Type"] == type_order[0]]
        factory_df = df_all[df_all["Type"] == type_order[1]]
        packing_df = df_all[df_all["Type"] == type_order[2]]

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
    st.info("📌 Upload file PDF để bắt đầu")
