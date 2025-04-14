import streamlit as st
st.set_page_config(page_title="NBA Test Dashboard", layout="centered")

st.title("✅ Hello from NBA Dashboard")

st.write("This is a minimal test to verify the app runs on Streamlit Cloud.")

# Load test DataFrame
data = {
    "Player": ["Nikola Jokic", "Luka Doncic", "Jayson Tatum"],
    "Points": [25, 33, 28],
    "Minutes": [34, 36, 35]
}

import pandas as pd
df = pd.DataFrame(data)

st.dataframe(df, use_container_width=True)

st.success("🎉 This minimal version is working!")

