
import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO
import zipfile

def extract_fields_from_text(text):
    data = {
        "Well Name": None,
        "Depth (ft)": None,
        "BIT DATA Size": None,
        "Hours": None,
        "ROP (ft/hr)": None,
        "Total Circulation Volume": None,
        "Oil Added (+)": None,
        "Water Added (+)": None,
        "Barite Added (+)": None,
        "Other Product Usage (+)": None,
        "Downhole/Seepage/Formation": None,
        "Evaporation": None,
        "PV": None,
        "YP": None,
        "Mud Flow (gpm)": None,
        "Mud Weight (ppg)": None
    }

    patterns = {
        "Well Name": r"Well Name and No\.?\s+(.*?)\s+Rig Name",
        "Depth (ft)": r"Bit Depth = ([\d,]+)\s*'",
        "BIT DATA Size": r"BIT DATA.*?Size\s*(\d+\s*\d+/\d+)",
        "Hours": r"Hours\s*(\d+\.?\d*)",
        "ROP (ft/hr)": r"ROP\s*ft/hr\s*(\d+\.?\d*)",
        "In Pits": r"In Pits\s*(\d+\.?\d*)",
        "In Hole": r"In Hole\s*(\d+\.?\d*)",
        "Oil Added \(\+\)": r"Oil Added \(\+\)\s*(\d+\.?\d*)",
        "Water Added \(\+\)": r"Water Added \(\+\)\s*(\d+\.?\d*)",
        "Barite Added \(\+\)": r"Barite Added \(\+\)\s*(\d+\.?\d*)",
        "Other Product Usage \(\+\)": r"Other Product Usage \(\+\)\s*(\d+\.?\d*)",
        "Downhole": r"Downhole.*?\s(-?\d+\.?\d*)",
        "Evaporation": r"Evaporation.*?\s(-?\d+\.?\d*)",
        "PV": r"PV\s*(\d+\.?\d*)",
        "YP": r"YP\s*(\d+\.?\d*)",
        "Mud Flow \(gpm\)": r"PUMP #\d+\s*(\d+)\s*gpm",
        "Mud Weight \(ppg\)": r"Mud WT\s*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*PPG"
    }

    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if field == "Mud Weight (ppg)":
                data[field] = float(match.group(1))
            elif field in ["Depth (ft)", "Mud Flow (gpm)", "ROP (ft/hr)"]:
                data[field] = int(match.group(1).replace(",", ""))
            elif field in ["In Pits", "In Hole"]:
                data[field] = float(match.group(1))
            else:
                data[field] = match.group(1).strip()

    if data.get("In Pits") is not None and data.get("In Hole") is not None:
        data["Total Circulation Volume"] = data["In Pits"] + data["In Hole"]

    data.pop("In Pits", None)
    data.pop("In Hole", None)

    return data

st.title("Mud Report PDF Extractor & Visualizer")

uploaded_files = st.file_uploader("Upload Mud Report PDFs", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    all_data = []
    file_buffer = BytesIO()
    with zipfile.ZipFile(file_buffer, "w") as zipf:
        for uploaded_file in uploaded_files:
            file_bytes = uploaded_file.read()
            zipf.writestr(uploaded_file.name, file_bytes)
            with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
                data = extract_fields_from_text(text)
                all_data.append(data)

    df = pd.DataFrame(all_data)
    st.subheader("Extracted Mud Report Data")
    st.dataframe(df)

    st.subheader("Well-to-Well Comparison")
    wells = df["Well Name"].dropna().unique().tolist()
    selected = st.multiselect("Compare Wells", wells, default=wells[:2])
    if selected:
        comp_df = df[df["Well Name"].isin(selected)].set_index("Well Name")
        st.line_chart(comp_df[["PV", "YP", "Mud Flow (gpm)", "ROP (ft/hr)"]])

    st.subheader("Additive Efficiency per Depth (bbl/ft)")
    with pd.option_context('mode.use_inf_as_na', True):
        df_eff = df.copy()
        df_eff["Oil/ft"] = df_eff["Oil Added (+)"].astype(float) / df_eff["Depth (ft)"].astype(float)
        df_eff["Water/ft"] = df_eff["Water Added (+)"].astype(float) / df_eff["Depth (ft)"].astype(float)
        df_eff["Barite/ft"] = df_eff["Barite Added (+)"].astype(float) / df_eff["Depth (ft)"].astype(float)
        df_eff["Other/ft"] = df_eff["Other Product Usage (+)"].astype(float) / df_eff["Depth (ft)"].astype(float)
        st.dataframe(df_eff[["Well Name", "Oil/ft", "Water/ft", "Barite/ft", "Other/ft"]])

    st.subheader("Fluid Additives Visualization")
    st.bar_chart(df.set_index("Well Name")[["Oil Added (+)", "Water Added (+)", "Barite Added (+)", "Other Product Usage (+)"]])

    st.subheader("Fluid Loss Alerts")
    alert_df = df[(df["Downhole/Seepage/Formation"].fillna(0) > 10) | (df["Evaporation"].fillna(0) > 10)]
    if not alert_df.empty:
        st.warning("⚠️ Potential fluid loss detected:")
        st.dataframe(alert_df)
    else:
        st.success("✅ No fluid loss issues detected.")

    st.subheader("Export Data")
    st.download_button("Download CSV", data=df.to_csv(index=False), file_name="mud_report_summary.csv")

    st.subheader("Export Original PDFs as ZIP")
    file_buffer.seek(0)
    st.download_button("Download ZIP", data=file_buffer, file_name="mud_reports_bundle.zip", mime="application/zip")
