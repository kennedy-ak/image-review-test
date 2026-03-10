import streamlit as st
import pandas as pd
import json
from pathlib import Path

DONE_FILE = Path("done_items.json")

def load_done():
    if DONE_FILE.exists():
        return set(json.loads(DONE_FILE.read_text()))
    return set()

def save_done(done_set):
    DONE_FILE.write_text(json.dumps(list(done_set)))

st.set_page_config(page_title="Product Image Review", layout="wide")
st.title("Product Image Review")

@st.cache_data
def load_data():
    df = pd.read_csv("catalog-v4-enum_rows.csv", usecols=["id", "product_name", "image_url", "product_url", "category", "sub_category"])
    df = df.dropna(subset=["id"])
    df["category"] = df["category"].fillna("Unknown")
    df["sub_category"] = df["sub_category"].fillna("Unknown")
    return df

df = load_data()

# Load done items
if "done_items" not in st.session_state:
    st.session_state.done_items = load_done()

# Sidebar controls
search = st.sidebar.text_input("Search by ID or Name")

categories = sorted(df["category"].unique())
selected_category = st.sidebar.selectbox("Category", ["All"] + categories)

if selected_category != "All":
    sub_categories = sorted(df[df["category"] == selected_category]["sub_category"].unique())
    selected_sub = st.sidebar.selectbox("Sub-category", ["All"] + sub_categories)
else:
    selected_sub = "All"

per_page = st.sidebar.selectbox("Items per page", [20, 50, 100, 200], index=1)
cols_count = st.sidebar.selectbox("Columns", [3, 4, 5, 6], index=1)

# Filter
filtered = df
if search:
    filtered = filtered[
        filtered["id"].astype(str).str.contains(search, case=False, na=False)
        | filtered["product_name"].astype(str).str.contains(search, case=False, na=False)
    ]
if selected_category != "All":
    filtered = filtered[filtered["category"] == selected_category]
if selected_sub != "All":
    filtered = filtered[filtered["sub_category"] == selected_sub]

total = len(filtered)
total_pages = max(1, -(-total // per_page))  # ceil division

st.sidebar.markdown(f"**{total}** products found")

page = st.sidebar.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)

start = (page - 1) * per_page
page_data = filtered.iloc[start : start + per_page]

st.caption(f"Showing {start + 1}–{min(start + per_page, total)} of {total} products  |  Page {page} of {total_pages}")

# Render grid
rows = [page_data.iloc[i : i + cols_count] for i in range(0, len(page_data), cols_count)]

for row_data in rows:
    cols = st.columns(cols_count)
    for i, (_, item) in enumerate(row_data.iterrows()):
        with cols[i]:
            img_url = item.get("image_url", "")
            product_url = item.get("product_url", "")
            product_id = item.get("id", "")
            product_name = item.get("product_name", "")

            if pd.notna(img_url) and img_url:
                st.image(img_url, use_container_width=True)
            else:
                st.markdown("*No image*")

            if pd.notna(product_name) and product_name:
                st.markdown(f"**{product_name}**")

            st.caption(f"`{product_id}`")

            # Done checkbox
            is_done = product_id in st.session_state.done_items
            if st.checkbox("✓ Done", key=f"done_{product_id}", value=is_done):
                if product_id not in st.session_state.done_items:
                    st.session_state.done_items.add(product_id)
                    save_done(st.session_state.done_items)
                    st.rerun()
            else:
                if product_id in st.session_state.done_items:
                    st.session_state.done_items.remove(product_id)
                    save_done(st.session_state.done_items)
                    st.rerun()

            if pd.notna(product_url) and product_url:
                st.markdown(f"[View Product →]({product_url})")
