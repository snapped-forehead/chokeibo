"""ちょけいぼ - Webアプリ"""
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from flask import Flask, redirect, request, session, jsonify, render_template, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request

import sheets as sh
import summary as sm

BASE_DIR = Path(__file__).parent
TEMPLATE_DIR = BASE_DIR / 'templates'
CATEGORIES_FILE = BASE_DIR / 'categories.json'
CREDENTIALS_FILE = BASE_DIR / 'credentials.json'

# Railway環境では環境変数からcredentials.jsonを生成
_creds_env = os.environ.get('GOOGLE_CREDENTIALS')
if _creds_env and not CREDENTIALS_FILE.exists():
    CREDENTIALS_FILE.write_text(_creds_env, encoding='utf-8')

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file',
]

JST = timezone(timedelta(hours=9))

app = Flask(__name__, template_folder=str(TEMPLATE_DIR))
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ローカル開発時はHTTPを許可
if os.environ.get('FLASK_ENV') != 'production':
    os.environ.setdefault('OAUTHLIB_INSECURE_TRANSPORT', '1')


# ============================================================
# 認証ヘルパー
# ============================================================
def load_creds():
    """セッションからCredentialsを復元"""
    data = session.get('credentials')
    if not data:
        return None
    creds = Credentials(
        token=data['token'],
        refresh_token=data.get('refresh_token'),
        token_uri=data['token_uri'],
        client_id=data['client_id'],
        client_secret=data['client_secret'],
        scopes=data.get('scopes', SCOPES),
    )
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_creds(creds)
            return creds
        except Exception:
            session.pop('credentials', None)
            return None
    return None


def _save_creds(creds):
    session['credentials'] = {
        'token':         creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri':     creds.token_uri,
        'client_id':     creds.client_id,
        'client_secret': creds.client_secret,
        'scopes':        list(creds.scopes or SCOPES),
    }


def get_ss_id(creds):
    ss_id = session.get('ss_id')
    if not ss_id:
        ss_id = sh.find_or_create_spreadsheet(creds)
        session['ss_id'] = ss_id
    return ss_id


# ============================================================
# ルーティング
# ============================================================
@app.route('/')
def index():
    if load_creds() is None:
        return redirect(url_for('auth_login'))
    cats = json.loads(CATEGORIES_FILE.read_text(encoding='utf-8'))
    today = datetime.now(JST).strftime('%Y-%m-%d')
    return render_template('index.html', categories=cats, today=today)


@app.route('/api/submit', methods=['POST'])
def api_submit():
    creds = load_creds()
    if creds is None:
        return jsonify({'success': False, 'message': '認証が必要です'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'message': '不正なリクエストです'}), 400

    date_str = data.get('date', '').strip()
    amount   = int(data.get('amount', 0))
    category = data.get('category', '').strip()
    note     = data.get('note', '').strip()

    if not date_str or amount <= 0 or not category:
        return jsonify({'success': False, 'message': '日付・金額・勘定科目は必須です'}), 400

    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
        date_fmt = d.strftime('%Y/%m/%d')
    except ValueError:
        return jsonify({'success': False, 'message': '日付の形式が不正です'}), 400

    timestamp = datetime.now(JST).strftime('%Y/%m/%d %H:%M:%S')

    try:
        ss_id = get_ss_id(creds)
        sh.append_row(creds, ss_id, date_fmt, category, amount, note, timestamp)
        return jsonify({'success': True, 'message': '登録しました'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/summary')
def summary():
    if load_creds() is None:
        return redirect(url_for('auth_login'))
    return render_template('summary.html')


@app.route('/api/summary')
def api_summary():
    creds = load_creds()
    if creds is None:
        return jsonify({'success': False, 'message': '認証が必要です'}), 401
    try:
        ss_id = get_ss_id(creds)
        rows  = sh.get_all_rows(creds, ss_id)
        data  = sm.build_summary(rows)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/categories', methods=['GET', 'POST'])
def categories():
    if load_creds() is None:
        return redirect(url_for('auth_login'))
    if request.method == 'POST':
        new_cats = []
        names  = request.form.getlist('name[]')
        colors = request.form.getlist('color[]')
        ids    = request.form.getlist('id[]')
        import re, time
        for i, name in enumerate(names):
            name = name.strip()
            if not name:
                continue
            color = colors[i] if i < len(colors) else '#888888'
            if not re.match(r'^#[0-9a-fA-F]{6}$', color):
                color = '#888888'
            new_cats.append({
                'id':    int(ids[i]) if i < len(ids) and ids[i].isdigit() else int(time.time()) + i,
                'name':  name,
                'color': color,
            })
        if not new_cats:
            return redirect('/categories')
        CATEGORIES_FILE.write_text(
            json.dumps(new_cats, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        return redirect('/categories?saved=1')
    cats = json.loads(CATEGORIES_FILE.read_text(encoding='utf-8'))
    return render_template('categories.html', categories=cats, saved='saved' in request.args)


# ============================================================
# 認証
# ============================================================
@app.route('/auth/login')
def auth_login():
    flow = Flow.from_client_secrets_file(
        str(CREDENTIALS_FILE),
        scopes=SCOPES,
        redirect_uri=url_for('auth_callback', _external=True),
    )
    auth_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent',
    )
    session['oauth_state'] = state
    return redirect(auth_url)


@app.route('/auth/callback')
def auth_callback():
    state = session.get('oauth_state')
    flow = Flow.from_client_secrets_file(
        str(CREDENTIALS_FILE),
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('auth_callback', _external=True),
    )
    flow.fetch_token(authorization_response=request.url)
    _save_creds(flow.credentials)
    return redirect(url_for('index'))


@app.route('/auth/logout')
def auth_logout():
    session.clear()
    return redirect(url_for('auth_login'))


# ============================================================
# 起動
# ============================================================
if __name__ == '__main__':
    if not CATEGORIES_FILE.exists():
        CATEGORIES_FILE.write_text(json.dumps([
            {'id': 1, 'name': '食費',   'color': '#4A90D9'},
            {'id': 2, 'name': '交通費', 'color': '#5BA85A'},
            {'id': 3, 'name': '日用品', 'color': '#D97B4A'},
            {'id': 4, 'name': 'その他', 'color': '#95A5A6'},
        ], ensure_ascii=False, indent=2), encoding='utf-8')
    app.run(port=5000, debug=False)
