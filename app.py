import streamlit as st
import pandas as pd
import numpy as np
from streamlit_gsheets import GSheetsConnection
import time
from datetime import datetime
import pytz

# Establish connection (ensure the correct credentials and setup)
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Failed to connect to Google Sheets: {e}")

# Fetch data from Google Sheets
@st.cache_data(ttl=5)
def load_data(sheet_name="Sheet1"):
    try:
        data = conn.read(worksheet=sheet_name, usecols=[0, 1, 2, 3, 4])  # Added an extra column for Sheet2
        data = data.dropna(how="all")
        data = data.loc[:, ~data.columns.str.contains('^Unnamed')]
        if sheet_name == "Sheet1":
            # Ensure QUANTITY is numeric, replace non-numeric values with 0
            data['QUANTITY'] = pd.to_numeric(data['QUANTITY'], errors='coerce').fillna(0).astype(int)
        return data
    except Exception as e:
        st.error(f"Error fetching data from {sheet_name}: {e}")
        return pd.DataFrame()

def refresh():
    conn = st.connection("gsheets", type=GSheetsConnection, ttl=5)
    if conn is None:
        st.error("Failed to establish Google Sheets connection.")
    else:
        st.success("Google Sheets connection refreshed successfully.")
        time.sleep(1)
        st.rerun()

# New function to log inventory changes
def log_inventory_change(product, size, quantity, action):
    try:
        # Load existing log data
        log_data = load_data("Sheet2")
        local_tz=pytz.timezone('Asia/Manila')
        # Create new log entry
        new_entry = pd.DataFrame({
            'Date': [datetime.now(local_tz).strftime("%Y-%m-%d %I:%M %p")],
            'Product': [product],
            'Size': [size],
            'Quantity': [quantity],
            'Action': [action]
        })
        
        # Concatenate new entry with existing log data
        updated_log_data = pd.concat([log_data, new_entry], ignore_index=True)
        
        # Update Sheet2 with the new log data
        conn.update(worksheet="Sheet2", data=updated_log_data)
    except Exception as e:
        st.error(f"Error logging inventory change: {e}")

# Load the data
existing_data = load_data()

# Initialize session state for view toggle
if 'view_log' not in st.session_state:
    st.session_state.view_log = False

# Sidebar
with st.sidebar:
    st.subheader("Inventory Management")
    
    # Toggle button for view
    if st.button("Toggle View (Inventory Log / Full Inventory)"):
        st.session_state.view_log = not st.session_state.view_log
    
    if not st.session_state.view_log:
        st.subheader("Filter Products")

        # Extract unique product names for filtering
        product_names = existing_data['PRODUCT'].unique()

        # Select a product to filter
        selected_product = st.selectbox("Select a product to filter (or select 'All' to show all):", options=['All'] + list(product_names))

        # Filter data based on selected product if not 'All'
        if selected_product != 'All':
            filtered_data = existing_data[existing_data['PRODUCT'] == selected_product]
        else:
            filtered_data = existing_data.copy()

        # Extract unique sizes for the filtered data
        sizes = filtered_data['SIZE'].unique()

        # Select a size to filter
        selected_size = st.selectbox("Select a size to filter (or select 'All' to show all):", options=['All'] + list(sizes))

        # Apply size filter based on the selected size if not 'All'
        if selected_size != 'All':
            filtered_data = filtered_data[filtered_data['SIZE'] == selected_size]
            
        st.divider()
        
        # Add or remove products
        st.subheader("Update Inventory")

        # Select a product and size to update
        selected_product_to_update = st.selectbox("Select a product to update:", options=existing_data['PRODUCT'].unique(), key="product_update")
        
        # Filter sizes based on selected product
        sizes_for_product = existing_data[existing_data['PRODUCT'] == selected_product_to_update]['SIZE'].unique()
        selected_size_to_update = st.selectbox("Select a size to update:", options=sizes_for_product, key="size_update")

        # Get current quantity
        current_quantity = existing_data.loc[
            (existing_data['PRODUCT'] == selected_product_to_update) & 
            (existing_data['SIZE'] == selected_size_to_update), 
            'QUANTITY'
        ].values[0]

        st.write(f"Current quantity: {current_quantity}")

        # Select between Add or Remove
        action = st.radio("Choose action:", ("Add", "Remove"))

        # Input for quantity based on selected action
        if action == "Add":
            quantity = st.number_input("Quantity to Add:", min_value=0, value=0, step=1)
        else:  # Remove
            quantity = st.number_input("Quantity to Remove:", min_value=0, max_value=current_quantity, value=0, step=1)

        # Button to perform the selected action
        if st.button("Update Inventory"):
            if quantity > 0:
                if action == "Add":
                    new_quantity = current_quantity + quantity
                    success_message = f"Added {quantity} to {selected_product_to_update} (Size: {selected_size_to_update}). New quantity: {new_quantity}"
                else:  # Remove
                    new_quantity = current_quantity - quantity
                    success_message = f"Removed {quantity} from {selected_product_to_update} (Size: {selected_size_to_update}). New quantity: {new_quantity}"

                mask = (existing_data['PRODUCT'] == selected_product_to_update) & (existing_data['SIZE'] == selected_size_to_update)
                existing_data.loc[mask, 'QUANTITY'] = new_quantity
                conn.update(worksheet="Sheet1", data=existing_data)
                
                # Log the inventory change
                log_inventory_change(selected_product_to_update, selected_size_to_update, quantity, action)
                
                st.success(success_message)
                st.cache_data.clear()
                existing_data = load_data()
                filtered_data = existing_data.copy()  # Reset filtered data
                refresh()
            else:
                st.warning("Please enter a quantity greater than 0.")

# Main area
if st.session_state.view_log:
    st.title("Inventory Log (Sheet2)")
    log_data = load_data("Sheet2")
    st.dataframe(log_data, use_container_width=True, hide_index=True)
else:
    st.title("Current Inventory (Sheet1)")
    st.dataframe(filtered_data, use_container_width=True, hide_index=True)