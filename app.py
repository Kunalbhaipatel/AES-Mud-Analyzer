
import streamlit as st
import fitz
import re
import pandas as pd
import plotly.graph_objects as go

def safe_search(pattern, text, default="0"):
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else default

def extract_fields(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = "".join([page.get_text() for page in doc])

    data = {}
    data['Well Name'] = safe_search(r"Well Name and No\.\s*(.*?)\n", text)
", text)
    data['Rig Name'] = safe_search(r"Rig Name and No\.\s*(.*?)
", text)
    data['Contractor'] = safe_search(r"(HELMERICH & PAYNE.*?)
", text)
    data['Depth'] = safe_search(r"Drilled Depth\s+([\d,]+)", text).replace(",", "")
    data['Bit Size'] = safe_search(r"Bit Data.*?Size.*?
.*?(\d+\.\d+)", text)
    data['Drilling Hrs'] = safe_search(r"Hours\s+([\d.]+)", text)

    data['Mud Weight'] = safe_search(r"MUD WT\s+([\d.]+)", text)
    data['PV'] = safe_search(r"Plastic Viscosity\s*\(cp\)\s*([\d.]+)", text)
    data['YP'] = safe_search(r"Yield Point.*?=\s*([\d.]+)", text)
    data['Avg Temp'] = safe_search(r"Flowline Temperature\s*°F\s*([\d.]+)", text)

    data['Base Oil'] = safe_search(r"Oil Added\s*\(\+\)\s*([\d.]+)", text)
    data['Water'] = safe_search(r"Water Added\s*\(\+\)\s*([\d.]+)", text)
    data['Barite'] = safe_search(r"Barite Added\s*\(\+\)\s*([\d.]+)", text)
    data['Chemical'] = safe_search(r"Other Product Usage\s*\(\+\)\s*([\d.]+)", text)
    data['SCE Loss'] = safe_search(r"Left on Cuttings\s*\(-\)\s*([\d.]+)", text)

    data['In Pits'] = safe_search(r"In Pits\s+([\d.]+)\s*bbl", text)
    data['In Hole'] = safe_search(r"In Hole\s+([\d.]+)\s*bbl", text)
    return data

def to_float(val):
    try:
        return float(val)
    except:
        return 0.0

st.title("📘 Clean BAKU Mud Report Analyzer")

uploaded_files = st.file_uploader("Upload Mud Report PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    records = []
    for file in uploaded_files:
        try:
            records.append(extract_fields(file))
        except Exception as e:
            st.error(f"Failed to parse {file.name}: {e}")

    if records:
        df = pd.DataFrame(records)
        for col in ['Depth', 'Drilling Hrs', 'Base Oil', 'Water', 'Barite', 'Chemical', 'SCE Loss',
                    'In Pits', 'In Hole', 'PV', 'YP', 'Mud Weight', 'Avg Temp']:
            df[col] = df[col].apply(to_float)

        df['Total Circ'] = df['In Pits'] + df['In Hole']
        df['Total Dilution'] = df[['Base Oil', 'Water', 'Chemical']].sum(axis=1)
        df['Discard Ratio'] = df['SCE Loss'] / df['Total Circ'].replace(0, 1)
        df['DSRE%'] = (df['Total Dilution'] / (df['Total Dilution'] + df['SCE Loss'].replace(0, 1))) * 100
        df['ROP'] = df['Depth'] / df['Drilling Hrs'].replace(0, 1)
        df['Mud Cutting Ratio'] = df['SCE Loss'] / df['Total Circ'].replace(0, 1) * 100

        st.dataframe(df)

        st.subheader("📊 Performance Chart")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df['Well Name'], y=df['ROP'], name='ROP'))
        fig.add_trace(go.Scatter(x=df['Well Name'], y=df['DSRE%'], name='DSRE%', mode='lines+markers'))
        fig.update_layout(barmode='group', title="ROP and DSRE% per Well")
        st.plotly_chart(fig, use_container_width=True)
