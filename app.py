import streamlit as st
import pandas as pd
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import os

load_dotenv()

# Database connection
DB_URL = os.getenv("DB_URL")

def get_db_connection():
    return psycopg2.connect(DB_URL)

def init_db():
    """Create the done_items and updated_images tables if they don't exist."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS done_items (
            product_id VARCHAR(255) PRIMARY KEY,
            done_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS updated_images (
            product_id VARCHAR(255) PRIMARY KEY,
            product_name TEXT,
            new_image_url TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def load_done():
    """Load all done product IDs from the database."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT product_id FROM done_items")
        done_set = {row[0] for row in cur.fetchall()}
        cur.close()
        conn.close()
        return done_set
    except Exception as e:
        st.error(f"Database error: {e}")
        return set()

def mark_done(product_id, is_done):
    """Mark a product as done or not done in the database."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if is_done:
            cur.execute("""
                INSERT INTO done_items (product_id)
                VALUES (%s)
                ON CONFLICT (product_id) DO NOTHING
            """, (product_id,))
        else:
            cur.execute("DELETE FROM done_items WHERE product_id = %s", (product_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"Database error: {e}")

def save_updated_image(product_id, product_name, new_image_url):
    """Save an updated image URL to the database."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO updated_images (product_id, product_name, new_image_url)
            VALUES (%s, %s, %s)
            ON CONFLICT (product_id)
            DO UPDATE SET product_name = EXCLUDED.product_name,
                          new_image_url = EXCLUDED.new_image_url,
                          updated_at = CURRENT_TIMESTAMP
        """, (str(product_id), str(product_name), new_image_url))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"Database error: {e}")

def load_updated_images_csv():
    """Load all updated images from the database as CSV string."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT product_id, product_name, new_image_url FROM updated_images ORDER BY updated_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    df = pd.DataFrame(rows, columns=["id", "product_name", "new_image_url"])
    return df.to_csv(index=False)

# Initialize database table
init_db()

st.set_page_config(page_title="Product Image Review", layout="wide")
st.title("Product Image Review")

@st.cache_data
def load_data():
    df = pd.read_csv("catalog-v4-enum_rows.csv", usecols=["id", "product_name", "description", "image_url", "product_url", "category", "sub_category"])
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

st.sidebar.markdown("---")
st.sidebar.download_button(
    label="Download Updated Images CSV",
    data=load_updated_images_csv(),
    file_name="updated_images.csv",
    mime="text/csv",
)
st.sidebar.markdown("---")

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
            description = item.get("description", "")

            if pd.notna(img_url) and img_url:
                st.image(img_url, use_container_width=True)
            else:
                st.markdown("*No image*")

            if pd.notna(product_name) and product_name:
                st.markdown(f"**{product_name}**")

            if pd.notna(description) and description:
                st.caption(description)

            st.caption(f"`{product_id}`")

            if pd.notna(product_url) and product_url:
                st.markdown(f"[View Product →]({product_url})")

            # Editable image URL field
            new_url = st.text_input(
                "Image URL",
                value=img_url if pd.notna(img_url) else "",
                key=f"img_url_{product_id}",
                label_visibility="collapsed",
                placeholder="Paste new image URL here",
            )

            if st.button("Save", key=f"save_{product_id}"):
                if new_url and new_url.strip():
                    save_updated_image(product_id, product_name, new_url.strip())
                    st.success("Saved!")
                else:
                    st.warning("Enter a URL first")

            # Done checkbox
            is_done = product_id in st.session_state.done_items
            new_is_done = st.checkbox("Done", key=f"done_{product_id}", value=is_done)

            # Update database if checkbox state changed
            if new_is_done != is_done:
                mark_done(product_id, new_is_done)
                if new_is_done:
                    st.session_state.done_items.add(product_id)
                else:
                    st.session_state.done_items.discard(product_id)
                st.rerun()
