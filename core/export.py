import io

import pandas as pd


def to_csv_bytes(df):
    buffer = io.BytesIO()
    buffer.write(df.to_csv(index=False).encode('utf-8-sig'))
    return buffer.getvalue()


def to_excel_bytes(df, sheet_name='Data'):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31] or 'Data')
    return buffer.getvalue()
