
import streamlit as st
import pandas as pd
import re
import pdfplumber
from io import BytesIO
import matplotlib.pyplot as plt
import numpy as np

# Extraction patterns
extraction_map = {
    'Well Name': r'Well Name and No\.\s*(.*?)\n',
    'Rig Name': r'Rig Name and No\.\s*(.*?)\n',
    'Contractor': r'HELMERICH & PAYNE, INC\.',
    'Depth': r'Drilled Depth\s+(\d{3,5})',
    'Bit Size': r'Bit Data.*?Size.*?\n.*?(\d+\.\d+)',
    'Drilling Hrs': r'Hours\s+([\d.]+)',
    'Mud Weight': r'MUD WT\s+([\d.]+)',
    'PV': r'Plastic Viscosity \(cp\).*?(\d+)',
    'YP': r'Yield Point.*?(\d+)',
    'Avg Temp': r'Flowline Temperature\s*°F\s*(\d+)',
    'Base Oil': r'Oil Added \(\+\)\s+([\d.]+)',
    'Water': r'Water Added \(\+\)\s+([\d.]+)',
    'Barite': r'Barite Added \(\+\)\s+([\d.]+)',
    'Chemical': r'Other Product Usage \(\+\)\s+([\d.]+)',
    'SCE Loss': r'Left on Cuttings \(-\)\s+([\d.]+)',
    'In Pits': r'In Pits\s+([\d.]+)\s*bbl',
    'In Hole': r'In Hole\s+([\d.]+)\s*bbl',
    'Formation Loss Flag': r'loss|gain|seepage',
}

def extract_pdf_data(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
    data = {}
    for field, pattern in extraction_map.items():
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        data[field] = match.group(1) if match and match.groups() else None
    try:
        data['Total Circ (bbl)'] = round(float(data.get('In Pits', 0)) + float(data.get('In Hole', 0)), 2)
    except:
        data['Total Circ (bbl)'] = None
    try:
        data['SCE Ratio (%)'] = round((float(data['SCE Loss']) / data['Total Circ (bbl)']) * 100, 2)
    except:
        data['SCE Ratio (%)'] = None
    try:
        data['Dilution (bbl)'] = float(data['Base Oil']) + float(data['Water'])
    except:
        data['Dilution (bbl)'] = None
    try:
        data['Dilution Ratio (%)'] = round(data['Dilution (bbl)'] / data['Total Circ (bbl)'] * 100, 2)
    except:
        data['Dilution Ratio (%)'] = None
    return data

def calculate_screen_wear(flowrate, screen_size, drilling_hrs):
    try:
        load = float(flowrate) / float(screen_size)
        return round(load * float(drilling_hrs), 2)
    except:
        return np.nan

st.title("🛢️ Drilling Fluid Report Analyzer")

uploaded_files = st.file_uploader("Upload Drilling PDF Reports", type="pdf", accept_multiple_files=True)

if uploaded_files:
    extracted_records = []
    for file in uploaded_files:
        record = extract_pdf_data(BytesIO(file.read()))
        record["Filename"] = file.name
        extracted_records.append(record)

    df = pd.DataFrame(extracted_records)
    st.success("✅ Extraction Complete!")

    st.subheader("📄 Extracted Report Data")
    st.dataframe(df)

    st.subheader("📊 Summary Metrics")
    summary = df[["Mud Weight", "PV", "YP", "Avg Temp", "SCE Ratio (%)", "Dilution Ratio (%)"]].astype(float)
    st.write(summary.describe().transpose())

    st.subheader("📈 Trends")
    fig, ax = plt.subplots()
    df['Mud Weight'] = pd.to_numeric(df['Mud Weight'], errors='coerce')
    df['SCE Ratio (%)'] = pd.to_numeric(df['SCE Ratio (%)'], errors='coerce')
    ax.plot(df["Filename"], df["Mud Weight"], label="Mud Weight (ppg)", marker='o')
    ax.plot(df["Filename"], df["SCE Ratio (%)"], label="SCE Loss %", marker='x')
    ax.set_xlabel("Report")
    ax.set_ylabel("Value")
    ax.set_title("Mud Weight vs SCE Loss")
    ax.legend()
    st.pyplot(fig)

    # Screen wear
    DEFAULT_SCREEN_SIZE = 200
    DEFAULT_FLOWRATE = 1000
    df["Deck 1 Wear"] = df.apply(lambda x: calculate_screen_wear(DEFAULT_FLOWRATE, DEFAULT_SCREEN_SIZE, x["Drilling Hrs"]), axis=1)
    df["Deck 2 Wear"] = df.apply(lambda x: calculate_screen_wear(DEFAULT_FLOWRATE, DEFAULT_SCREEN_SIZE, x["Drilling Hrs"]), axis=1)

    st.subheader("🛠️ Deck-Wise Shaker Screen Wear Index")
    wear_df = df[["Filename", "Deck 1 Wear", "Deck 2 Wear"]].set_index("Filename")
    st.bar_chart(wear_df)

    st.subheader("📊 Well-to-Well Comparison Summary")
    comparison_df = df[[
        "Filename", "Mud Weight", "PV", "YP", "Avg Temp",
        "SCE Ratio (%)", "Dilution Ratio (%)", "Deck 1 Wear", "Deck 2 Wear"
    ]].copy()
    comparison_df["Avg Screen Wear"] = comparison_df[["Deck 1 Wear", "Deck 2 Wear"]].mean(axis=1)
    comparison_df.set_index("Filename", inplace=True)

    st.write("🔍 Normalized Comparison (color coded)")
    styled = comparison_df.style.background_gradient(cmap="YlGnBu")
    st.dataframe(styled)

    st.download_button(
        label="📥 Download Comparison as CSV",
        data=comparison_df.to_csv().encode('utf-8'),
        file_name="well_comparison.csv",
        mime='text/csv'
    )
