import numpy as np
import streamlit as st
import base64
import camelot as cam
import pandas as pd
from io import BytesIO
import re



st.set_page_config(layout="wide", initial_sidebar_state="expanded", page_title="Bank Statement Table Extractor", page_icon=None)

st.title("Bank Statement Table Extractor")
st.subheader("")

input_pdf = st.file_uploader(label="Upload your pdf here", type='pdf')

st.markdown("### Page Number")

page_numbers_input = st.text_input("Enter the page numbers separated by commas (e.g., 1, 3, 5)", value="1")

st.markdown("### Tweaking")
rowtol = st.number_input("Enter row tweaking parameter : ", value=5.00)

coltol = st.number_input("Enter column tweaking parameter : ", value=1.00)

edgetol = st.number_input("Enter egde tweaking parameter : ", value=50.00)

# Preprocessing options
 
preprocess_type = st.selectbox("Select Preprocessing Type", ["Type 1", "Barclays", "HSBC1", "HSBC2" ,"Type5","Type6"])  

def extract_tables_from_pages(pages):
    all_tables = []
    for page_num in pages:
        tables = cam.read_pdf("input.pdf", pages=str(page_num), flavor='stream', split_text=True, row_tol=rowtol, column_tol=coltol, edge_tol=edgetol)
        all_tables.extend(tables)
    return all_tables

def preprocess_data(df, preprocess_type):
    if preprocess_type == "Type 1":
        pass
    elif preprocess_type == "Barclays":
        indices_to_check = [0, 2, 3, 4]
        last_non_empty_row = None
        if 3 >= len(df.columns):
            return df

        for index, row in df.iterrows():
            if all(row[i] == '' or pd.isnull(row[i]) for i in indices_to_check):
                if last_non_empty_row is not None:
                    # Convert the cell value to string explicitly
                    df.at[last_non_empty_row, 1] = str(df.at[last_non_empty_row, 1]) + ' ' + str(row[1])
                    # Clear the current row
                    df.iloc[index] = None

            else:
                last_non_empty_row = index
        # Remove rows where all columns in indices_to_check are empty
        df = df.dropna(subset=[df.columns[i] for i in indices_to_check if i < len(df.columns)], how='all')
        df.iloc[:, 0] = df.iloc[:, 0].mask(df.iloc[:, 0] == '').ffill()
        return df
    elif preprocess_type == "HSBC1":
        def extract_and_remove_date(cell):
            # Convert cell to string (if it's not already)
            cell = str(cell)
            
            match = re.search(r'\b(\d+\s\w+\s\d+)\b', cell)
            if match:
                date = match.group(1)
                cell = cell.replace(date, '').strip()
                return date, cell
            return None, cell

        # Extracting date and modifying original column
        df['Dates'], df[df.columns[0]] = zip(*df[df.columns[0]].apply(extract_and_remove_date))
        # Reordering columns directly
        df = df[['Dates'] + [col for col in df.columns if col != 'Dates']]
        df = df.reset_index(drop=True)
        rows_to_remove = []

        for i in range(1, len(df)):
            # Check if the cell at index 0 and 1 in the current row is either an empty string, None, or contains only spaces
            if (df.iloc[i, 0] is None or str(df.iloc[i, 0]).strip() == '') and (df.iloc[i, 1] is None or str(df.iloc[i, 1]).strip() == ''):
                # Check if the corresponding cells in the previous row are not empty strings or spaces or None
                if (df.iloc[i - 1, 0] is not None and str(df.iloc[i - 1, 0]).strip() != '') or (df.iloc[i - 1, 1] is not None and str(df.iloc[i - 1, 1]).strip() != ''):
                    # Join current row's data with the preceding row's data
                    for col in range(len(df.columns)):
                        if df.iloc[i, col] is not None and str(df.iloc[i, col]).strip() != '':
                            # Joining data with a space
                            df.iloc[i - 1, col] = str(df.iloc[i - 1, col]).strip() + " " + str(df.iloc[i, col]).strip()
                    # Mark the current row for removal
                    rows_to_remove.append(i)

        # Remove marked rows
        df = df.drop(rows_to_remove).reset_index(drop=True)
        df.iloc[:, 0] = df.iloc[:, 0].mask(df.iloc[:, 0] == '').ffill()

    elif preprocess_type == "HSBC2":
        rows_to_remove = []

        for i in range(1, len(df)):

            if (df.iloc[i, 0] is None or str(df.iloc[i, 0]).strip() == '') and (df.iloc[i, 1] is None or str(df.iloc[i, 1]).strip() == ''):
                if (df.iloc[i - 1, 0] is not None and str(df.iloc[i - 1, 0]).strip() != '') or (df.iloc[i - 1, 1] is not None and str(df.iloc[i - 1, 1]).strip() != ''):
                    for col in range(len(df.columns)):
                        if df.iloc[i, col] is not None and str(df.iloc[i, col]).strip() != '':
                            df.iloc[i - 1, col] = str(df.iloc[i - 1, col]).strip() + " " + str(df.iloc[i, col]).strip()
                    rows_to_remove.append(i)

        # Remove marked rows
        df = df.drop(rows_to_remove).reset_index(drop=True)
        df.iloc[:, 0] = df.iloc[:, 0].mask(df.iloc[:, 0] == '').ffill()
    elif preprocess_type == "Type5":
        pass
    elif preprocess_type == "Type6":
        pass        
    return df


def get_table_download_link(df, uploaded_filename):
    output = BytesIO()
    df.to_excel(output, sheet_name='table', index=False)
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{uploaded_filename}.xlsx">Download Excel File</a>'
    return href


if input_pdf is not None:
    uploaded_filename = input_pdf.name.split('.')[0]  # Extracting the filename without extension
    with open("input.pdf", "wb") as f:
        f.write(input_pdf.read())

    # selected_page_numbers = [int(page.strip()) for page in page_numbers_input.split(',')]
    selected_page_numbers = [int(page.strip()) for page in page_numbers_input.split(',') if page.strip()]


    all_extracted_tables = extract_tables_from_pages(selected_page_numbers)

    st.markdown("### Number of Tables")
    st.write(len(all_extracted_tables))

    if len(all_extracted_tables) > 0:
        st.markdown('### Output Table')

        # Combine all tables from multiple pages into one DataFrame
        combined_df = pd.concat([table.df for table in all_extracted_tables], ignore_index=True)

        preprocessed_combined_df = preprocess_data(combined_df, preprocess_type)

        edited_df = st.data_editor(preprocessed_combined_df, use_container_width=True)
        
        download_link = get_table_download_link(preprocessed_combined_df, uploaded_filename)
        st.markdown(download_link, unsafe_allow_html=True)
     

