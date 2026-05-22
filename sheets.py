"""Google Sheets API ラッパー"""
from googleapiclient.discovery import build

SPREADSHEET_TITLE = '取引入力データ'
SHEET_NAME = '取引'
HEADERS = ['日付', '勘定科目', '金額', '摘要', '登録日時']


def get_service(creds):
    return build('sheets', 'v4', credentials=creds)


def get_drive_service(creds):
    return build('drive', 'v3', credentials=creds)


def find_or_create_spreadsheet(creds):
    """スプレッドシートを検索、なければ作成してIDを返す"""
    drive = get_drive_service(creds)
    results = drive.files().list(
        q=f"name='{SPREADSHEET_TITLE}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
        fields='files(id, name)'
    ).execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']

    # 新規作成
    service = get_service(creds)
    spreadsheet = service.spreadsheets().create(body={
        'properties': {'title': SPREADSHEET_TITLE},
        'sheets': [{'properties': {'title': SHEET_NAME}}]
    }).execute()
    ss_id = spreadsheet['spreadsheetId']

    # ヘッダー行を書き込む
    service.spreadsheets().values().update(
        spreadsheetId=ss_id,
        range=f'{SHEET_NAME}!A1',
        valueInputOption='USER_ENTERED',
        body={'values': [HEADERS]}
    ).execute()

    # ヘッダー行を太字・背景色で装飾
    service.spreadsheets().batchUpdate(
        spreadsheetId=ss_id,
        body={'requests': [{
            'repeatCell': {
                'range': {'sheetId': 0, 'startRowIndex': 0, 'endRowIndex': 1},
                'cell': {
                    'userEnteredFormat': {
                        'backgroundColor': {'red': 0.17, 'green': 0.24, 'blue': 0.31},
                        'textFormat': {'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}, 'bold': True}
                    }
                },
                'fields': 'userEnteredFormat(backgroundColor,textFormat)'
            }
        }]}
    ).execute()

    return ss_id


def append_row(creds, ss_id, date, category, amount, note, timestamp):
    """1行追記"""
    service = get_service(creds)
    service.spreadsheets().values().append(
        spreadsheetId=ss_id,
        range=f'{SHEET_NAME}!A1',
        valueInputOption='USER_ENTERED',
        insertDataOption='INSERT_ROWS',
        body={'values': [[date, category, amount, note, timestamp]]}
    ).execute()


def get_all_rows(creds, ss_id):
    """全データ取得（ヘッダー除く）"""
    service = get_service(creds)
    result = service.spreadsheets().values().get(
        spreadsheetId=ss_id,
        range=f'{SHEET_NAME}!A2:E'
    ).execute()
    return result.get('values', [])
