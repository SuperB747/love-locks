from flask import Flask, render_template, request, redirect, url_for, session, send_file
import sqlite3
import os
import uuid
from datetime import datetime
import qrcode
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # ⚠️ 실제 서비스에서는 환경변수로 분리 권장

DB_PATH = 'data/locks.db'
LANGUAGES = ['en', 'ko']

# 🔧 DB 초기화 함수
def init_db():
    if not os.path.exists('data'):
        os.makedirs('data')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locks (
            id TEXT PRIMARY KEY,
            name1 TEXT NOT NULL,
            name2 TEXT NOT NULL,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# 🌐 언어 설정 미들웨어
@app.before_request
def set_language():
    lang = request.args.get('lang')
    if lang in LANGUAGES:
        session['lang'] = lang
    elif 'lang' not in session:
        session['lang'] = 'en'  # 기본값

# 🏠 메인 페이지
@app.route('/')
def index():
    return render_template('index.html', lang=session.get('lang', 'en'))

# 🔐 자물쇠 생성
@app.route('/create', methods=['POST'])
def create_lock():
    name1 = request.form.get('name1', '').strip()
    name2 = request.form.get('name2', '').strip()
    message = request.form.get('message', '').strip()

    if name1 and name2:
        lock_id = str(uuid.uuid4())[:8]
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO locks (id, name1, name2, message) VALUES (?, ?, ?, ?)',
                       (lock_id, name1, name2, message))
        conn.commit()
        conn.close()
        return redirect(url_for('view_lock', lock_id=lock_id))
    return redirect(url_for('index'))

# 🔍 자물쇠 상세 보기
@app.route('/lock/<lock_id>')
def view_lock(lock_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT name1, name2, message, created_at FROM locks WHERE id = ?', (lock_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        created_at = row[3]
        d_day = (datetime.utcnow() - datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")).days
        return render_template(
            'view_lock.html',
            lock_id=lock_id,
            name1=row[0],
            name2=row[1],
            message=row[2],
            created_at=created_at,
            d_day=d_day,
            lang=session.get('lang', 'en')
        )
    return "Lock not found", 404

# 🗂 전체 자물쇠 보기 + 검색 필터
@app.route('/browse')
def browse_locks():
    query = request.args.get('query', '').strip()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if query:
        cursor.execute('''
            SELECT id, name1, name2, message, created_at
            FROM locks
            WHERE name1 LIKE ? OR name2 LIKE ? OR message LIKE ?
            ORDER BY created_at DESC
        ''', (f'%{query}%', f'%{query}%', f'%{query}%'))
    else:
        cursor.execute('SELECT id, name1, name2, message, created_at FROM locks ORDER BY created_at DESC')

    rows = cursor.fetchall()
    conn.close()

    return render_template(
        'browse.html',
        locks=rows,
        query=query,
        lang=session.get('lang', 'en')
    )

# 🌐 언어 전환
@app.route('/set_language/<lang>')
def set_lang(lang):
    if lang in LANGUAGES:
        session['lang'] = lang
    return redirect(url_for('index'))

# 📦 JS용 언어 JSON 파일 제공
@app.route('/locales/<lang>.json')
def get_locale(lang):
    if lang not in LANGUAGES:
        lang = 'en'
    return app.send_static_file(f'locales/{lang}.json')

# 📱 QR 코드 생성 (Render URL 호환)
@app.route('/qr/<lock_id>')
def generate_qr(lock_id):
    base_url = request.url_root.rstrip('/')
    lock_url = base_url + url_for('view_lock', lock_id=lock_id)

    qr_img = qrcode.make(lock_url)
    buf = BytesIO()
    qr_img.save(buf, format='PNG')
    buf.seek(0)

    return send_file(buf, mimetype='image/png')

# 🚀 실행
if __name__ == '__main__':
    init_db()
    app.run(debug=True)