import streamlit as st
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
import pandas as pd
import re
import io
import base64

def process_empty_rows(df):
    # Function to process empty rows in a DataFrame
    indices_to_check = [0, 2, 3, 4]
    last_non_empty_row = None
    for index, row in df.iterrows():
        if all(df.columns[i] in row and (pd.isna(row[i]) or row[i] == '') for i in indices_to_check):
            if last_non_empty_row is not None and df.columns[1] in df:
                if not pd.isna(df.at[last_non_empty_row, df.columns[1]]) and not pd.isna(row[df.columns[1]]):
                    df.at[last_non_empty_row, df.columns[1]] = str(df.at[last_non_empty_row, df.columns[1]]) + ' ' + str(row[df.columns[1]])
                df = df.drop(index)
        else:
            last_non_empty_row = index
    df = df.dropna(subset=[df.columns[i] for i in indices_to_check if i < len(df.columns)], how='all')
    df.iloc[:, 0] = df.iloc[:, 0].mask(df.iloc[:, 0] == '').ffill()
    df.iloc[:, 0] = df.iloc[:, 0].str.replace('  ', ' ')
    df.iloc[:, 0] = df.iloc[:, 0].apply(lambda s: re.sub(r'(\d)\s(\d)', r'\1\2', s) if isinstance(s, str) else s)
    return df

def separate_date_description(row):
    # Function to separate date and description in a DataFrame row
    cell = row['Date']
    description = row['Descriptions']
    
    if isinstance(cell, str):
        match = re.match(r'(\d{1,2} \w+)', cell)
        if match:
            date = match.group(1)
            if not description:
                description = cell[len(date):].strip()
            return pd.Series([date, description])
    
    return pd.Series([cell, description])

def process_pdf_and_get_dataframe(file_path):
    # Function to process the uploaded PDF and return the combined DataFrame
    endpoint = "https://ao-document-intelligence.cognitiveservices.azure.com/"
    key = "d66dc755d5e44a4caca99b434831ca99"
    
    document_analysis_client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    
    with open(file_path, "rb") as f:
        poller = document_analysis_client.begin_analyze_document("prebuilt-document", f.read())
        result = poller.result()
    
    tables_data = []
    
    if result.tables:
        for table in result.tables:
            if table.column_count > 3:
                data = []
                for row_idx in range(table.row_count):
                    row_data = []
                    skip_row = False
                    for column_idx in range(table.column_count):
                        cell = [cell for cell in table.cells if cell.row_index == row_idx and cell.column_index == column_idx]
                        if cell:
                            cell_content = cell[0].content.strip()
                            cell_content = cell_content.replace("1)", "").replace(")))", "").replace("%", "").replace("", "").replace(":unselected:", "").replace(":selected:", "").replace("=", "").replace("- ", "")
                            if "Balance carried forward" in cell_content or \
                               "Start Balance" in cell_content or \
                               "brought forward" in cell_content or \
                               "carried forward" in cell_content or \
                               "Continued" in cell_content or \
                               "Balance brought forward" in cell_content or \
                               "Payments/Receipts" in cell_content:
                                skip_row = True
                                break
                            else:
                                row_data.append(cell_content)
                        else:
                            row_data.append(None)
    
                    if not skip_row:
                        data.append(row_data)
    
                if data:
                    df = pd.DataFrame(data[1:], columns=data[0])
                    df = df.dropna(how='all')
                    second_last_col_name = df.columns[-2]
                    if "Money in £" not in second_last_col_name:
                        last_col_name = df.columns[-1]

                        # Merge the last and second last columns
                        df[last_col_name] = df.iloc[:, -2].fillna('') + " " + df.iloc[:, -1].fillna('')
                        df[last_col_name] = df[last_col_name].str.strip()

                        # Drop the second last column
                        df.drop(df.columns[-2], axis=1, inplace=True)

                        # Rename the merged column
                        df.rename(columns={df.columns[-1]: last_col_name}, inplace=True)                    

                    df = df.rename(columns={df.columns[0]: 'Date', 
                                            df.columns[-1]: 'Balance £', 
                                            df.columns[-2]: 'Money in £', 
                                            df.columns[-3]: 'Money out £'})
                    df['Descriptions'] = df.iloc[:, 1:-3].apply(lambda x: ' '.join(x.dropna().astype(str)), axis=1)
                    cols=["Date", "Descriptions", "Money out £", "Money in £", "Balance £"]
                    df = df[cols]
                    df = process_empty_rows(df)
                    df[['Date', 'Descriptions']] = df.apply(separate_date_description, axis=1)
                    if len(df.columns) != 5:
                        continue
                    tables_data.append(df)
    
    combined_df = pd.concat(tables_data, ignore_index=True)
    return combined_df

def get_table_download_link(df, filename):
    # Function to generate a download link for the DataFrame as an Excel file with the original filename
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False)
    excel_buffer.seek(0)
    excel_binary = excel_buffer.getvalue()
    excel_base64 = base64.b64encode(excel_binary).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{excel_base64}" download="{filename}.xlsx">Download Excel file</a>'
    return href


# Streamlit App
st.set_page_config(layout="wide", initial_sidebar_state="expanded", page_title="Bank Statement Table Extractor", page_icon=None)
st.title("PDF Document Analyzer")

uploaded_file = st.file_uploader("Upload a PDF file", type="pdf")

if uploaded_file is not None:
    # Save the uploaded file temporarily
    with open("temp.pdf", "wb") as f:
        f.write(uploaded_file.getvalue())

    st.text("Processing the uploaded PDF...")
    combined_df = process_pdf_and_get_dataframe("temp.pdf")

    st.subheader("Combined DataFrame from PDF:")
    st.data_editor(combined_df, use_container_width=True)

    # Download Button for Excel
    st.markdown(get_table_download_link(combined_df, uploaded_file.name), unsafe_allow_html=True)

