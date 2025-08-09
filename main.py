import telebot
import requests
import json
import os
import time
import sqlite3
import threading
import platform
import psutil
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

# إعدادات البوت التلجرام
TOKEN = "7534513174:AAGJch5n9wpye0eAz4FETpa839L9SvOKDa8"
bot = telebot.TeleBot(TOKEN)

# إعدادات لوحة التحكم
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "securepassword123"
PANEL_PORT = 5000

# إعداد تطبيق Flask للوحة التحكم
app = Flask(__name__, template_folder='templates')
app.secret_key = 'super_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'

# قاعدة البيانات
DB_FILE = "bot_data.db"

# تهيئة قاعدة البيانات
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # حذف الجدول القديم إذا كان موجودًا
    cursor.execute('DROP TABLE IF EXISTS allowed_groups')
    
    # إنشاء الجداول المدمجة
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS allowed_users (
        user_id TEXT PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        usage_count INTEGER DEFAULT 0,
        last_used REAL
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS allowed_groups (
        chat_id TEXT PRIMARY KEY,
        group_name TEXT,
        added_by TEXT,
        added_time REAL,
        status TEXT DEFAULT 'active'
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bot_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS api_settings (
        api_name TEXT PRIMARY KEY,
        api_url TEXT
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS team_members (
        name TEXT PRIMARY KEY,
        role TEXT,
        telegram TEXT
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL,
        type TEXT,
        message TEXT
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS like_history (
        uid TEXT PRIMARY KEY,
        timestamp REAL
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS visit_history (
        uid TEXT PRIMARY KEY,
        timestamp REAL
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bot_stats (
        key TEXT PRIMARY KEY,
        value INTEGER
    )''')
    
    # تهيئة الإعدادات
    cursor.execute('''
    INSERT OR IGNORE INTO bot_settings (key, value) 
    VALUES 
        ('bot_enabled', 'true'),
        ('command_like_enabled', 'true'),
        ('command_visit_enabled', 'true'),
        ('command_info_enabled', 'true'),
        ('command_check_enabled', 'true'),
        ('command_panel_enabled', 'true'),
        ('welcome_message', ?)
    ''', (get_default_welcome_message(),))
    
    # تهيئة إعدادات الـ API
    default_apis = [
        ('like_api', 'https://likes.vercel.app/like'),
        ('visit_api', 'https://visit-taupe.vercel.app/visit'),
        ('region_api', 'https://aditya-region-v12op.onrender.com/region'),
        ('info_api', 'https://ff-player-info.vercel.app/player-info'),
        ('outfit_api', 'https://ff-outfit-image.vercel.app/outfit-image'),
        ('ban_check_api', 'https://ch9ayfa-ban-visit.vercel.app/ban_visit')
    ]
    
    for api in default_apis:
        cursor.execute('''
        INSERT OR IGNORE INTO api_settings (api_name, api_url)
        VALUES (?, ?)
        ''', api)
    
    # تهيئة فريق العمل
    default_team = [
        ('BLRXH4RDIXX', 'المطور الرئيسي', 'https://t.me/BLRXH4RDIXX')
    ]
    
    for member in default_team:
        cursor.execute('''
        INSERT OR IGNORE INTO team_members (name, role, telegram)
        VALUES (?, ?, ?)
        ''', member)
    
    # تهيئة الإحصائيات
    cursor.execute('''
    INSERT OR IGNORE INTO bot_stats (key, value) 
    VALUES 
        ('total_likes', 0),
        ('total_visits', 0),
        ('total_info_requests', 0),
        ('total_check_requests', 0),
        ('start_time', ?)
    ''', (time.time(),))
    
    conn.commit()
    conn.close()
    log_event('info', 'تم تهيئة قاعدة البيانات')

# الحصول على رسالة الترحيب الافتراضية
def get_default_welcome_message():
    return """
✨ *مرحباً بك في بوت FREE FIRE الرسمي* ✨

⚡ *الأوامر المتاحة:*
🔹 `/like UID` - إرسال إعجابات للاعب
🔹 `/visit UID` - إرسال زيارات للاعب
🔹 `/info UID` - معلومات اللاعب الكاملة مع الزي
🔹 `/check UID` - التحقق من حظر اللاعب

📌 *ملاحظات هامة:*
- يمكن استخدام أي رقم لاعب صحيح
- الأوامر تعمل في المجموعات المسموحة فقط
- لكل UID يمكن إرسال إعجابات أو زيارات مرة واحدة فقط كل 24 ساعة
- للاستفسارات: [BLRXH4RDIXX](https://t.me/BLRXH4RDIXX)

🔥 *مميزات البوت:*
✔ إرسال إعجابات فورية
✔ إرسال زيارات فورية
✔ عرض معلومات اللاعب كاملة مع الزي
✔ التحقق من حالة الحظر
✔ دعم متعدد اللغات
✔ سرعة في التنفيذ

📅 *آخر تحديث: 2025-9-8*
    """

# تسجيل الأحداث
def log_event(event_type, message):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO logs (timestamp, type, message) VALUES (?, ?, ?)', 
                  (time.time(), event_type, message))
    conn.commit()
    conn.close()

# دوال الوصول للبيانات
def get_db_connection():
    return sqlite3.connect(DB_FILE)

def get_setting(key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM bot_settings WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def update_setting(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR REPLACE INTO bot_settings (key, value)
    VALUES (?, ?)
    ''', (key, value))
    conn.commit()
    conn.close()
    log_event('info', f'تم تحديث الإعداد: {key} = {value}')

def get_api_url(api_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT api_url FROM api_settings WHERE api_name = ?', (api_name,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def update_api_url(api_name, api_url):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR REPLACE INTO api_settings (api_name, api_url)
    VALUES (?, ?)
    ''', (api_name, api_url))
    conn.commit()
    conn.close()
    log_event('info', f'تم تحديث API: {api_name} -> {api_url}')

def get_all_apis():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM api_settings')
    apis = cursor.fetchall()
    conn.close()
    
    formatted_apis = []
    for api in apis:
        formatted_apis.append({
            'name': api[0],
            'url': api[1]
        })
    return formatted_apis

def get_welcome_message():
    return get_setting('welcome_message') or get_default_welcome_message()

def record_user_usage(user_id, username, first_name, last_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    current_time = time.time()
    
    cursor.execute('''
    INSERT OR IGNORE INTO allowed_users (user_id, username, first_name, last_name, usage_count, last_used)
    VALUES (?, ?, ?, ?, 0, ?)
    ''', (user_id, username, first_name, last_name, current_time))
    
    cursor.execute('''
    UPDATE allowed_users 
    SET usage_count = usage_count + 1, last_used = ?
    WHERE user_id = ?
    ''', (current_time, user_id))
    
    conn.commit()
    conn.close()
    log_event('info', f'تم تسجيل استخدام المستخدم: {user_id}')

def get_user_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT user_id, username, first_name, last_name, usage_count, last_used 
    FROM allowed_users 
    ORDER BY last_used DESC
    ''')
    users = cursor.fetchall()
    conn.close()
    
    formatted_users = []
    for user in users:
        formatted_users.append({
            'user_id': user[0],
            'username': user[1] or 'N/A',
            'first_name': user[2] or 'N/A',
            'last_name': user[3] or 'N/A',
            'usage_count': user[4],
            'last_used': datetime.fromtimestamp(user[5]).strftime('%Y-%m-%d %H:%M:%S') if user[5] else 'N/A'
        })
    
    return formatted_users

def add_allowed_group(chat_id, group_name, added_by):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT OR REPLACE INTO allowed_groups (chat_id, group_name, added_by, added_time)
        VALUES (?, ?, ?, ?)
        ''', (chat_id, group_name, added_by, time.time()))
        conn.commit()
        log_event('info', f'تمت إضافة مجموعة: {group_name} ({chat_id})')
        return True
    except Exception as e:
        log_event('error', f'خطأ في إضافة مجموعة: {str(e)}')
        return False
    finally:
        conn.close()

def get_allowed_groups():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id, group_name, added_by, added_time FROM allowed_groups')
    groups = cursor.fetchall()
    conn.close()
    
    formatted_groups = []
    for group in groups:
        formatted_groups.append({
            'chat_id': group[0],
            'group_name': group[1] or 'N/A',
            'added_by': group[2] or 'N/A',
            'added_time': datetime.fromtimestamp(group[3]).strftime('%Y-%m-%d %H:%M:%S') if group[3] else 'N/A'
        })
    
    return formatted_groups

def remove_allowed_group(chat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM allowed_groups WHERE chat_id = ?', (chat_id,))
        conn.commit()
        log_event('info', f'تم حذف مجموعة: {chat_id}')
        return cursor.rowcount > 0
    except Exception as e:
        log_event('error', f'خطأ في حذف مجموعة: {str(e)}')
        return False
    finally:
        conn.close()

def get_bot_performance():
    # وقت تشغيل البوت
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM bot_stats WHERE key = "start_time"')
    row = cursor.fetchone()
    
    if row:
        start_time = float(row[0])
    else:
        start_time = time.time()
    
    uptime_seconds = time.time() - start_time
    uptime_str = str(timedelta(seconds=int(uptime_seconds)))
    
    # إحصائيات الاستخدام
    cursor.execute('SELECT SUM(value) FROM bot_stats WHERE key IN ("total_likes", "total_visits", "total_info_requests", "total_check_requests")')
    total_commands = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM allowed_users')
    total_users = cursor.fetchone()[0] or 0
    
    conn.close()
    
    # معلومات النظام
    cpu_percent = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    memory_percent = memory_info.percent
    
    return {
        'cpu_usage': cpu_percent,
        'memory_usage': memory_percent,
        'uptime': uptime_str,
        'process_time': uptime_seconds,
        'total_commands': total_commands,
        'total_users': total_users,
        'os': platform.system(),
        'python_version': platform.python_version()
    }

def increment_stat(stat_key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE bot_stats SET value = value + 1 WHERE key = ?
    ''', (stat_key,))
    conn.commit()
    conn.close()
    log_event('info', f'تم زيادة الإحصائيات: {stat_key}')

def is_bot_enabled():
    enabled = get_setting('bot_enabled')
    return enabled == 'true' if enabled else True

def set_bot_enabled(enabled):
    update_setting('bot_enabled', 'true' if enabled else 'false')

def is_command_enabled(command_name):
    enabled = get_setting(f'command_{command_name}_enabled')
    return enabled == 'true' if enabled else True

def set_command_enabled(command_name, enabled):
    update_setting(f'command_{command_name}_enabled', 'true' if enabled else 'false')

def add_team_member(name, role, telegram):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT OR REPLACE INTO team_members (name, role, telegram)
        VALUES (?, ?, ?)
        ''', (name, role, telegram))
        conn.commit()
        log_event('info', f'تمت إضافة عضو فريق: {name}')
        return True
    except Exception as e:
        log_event('error', f'خطأ في إضافة عضو فريق: {str(e)}')
        return False
    finally:
        conn.close()

def get_team_members():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name, role, telegram FROM team_members')
    team = cursor.fetchall()
    conn.close()
    
    formatted_team = []
    for member in team:
        formatted_team.append({
            'name': member[0],
            'role': member[1],
            'telegram': member[2]
        })
    return formatted_team

def get_logs(limit=100):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp, type, message FROM logs ORDER BY id DESC LIMIT ?', (limit,))
    logs = cursor.fetchall()
    conn.close()
    
    formatted_logs = []
    for log in logs:
        formatted_logs.append({
            'timestamp': datetime.fromtimestamp(log[0]).strftime('%Y-%m-%d %H:%M:%S'),
            'type': log[1],
            'message': log[2]
        })
    return formatted_logs

def is_user_allowed(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM allowed_users WHERE user_id = ?', (user_id,))
    allowed = cursor.fetchone() is not None
    conn.close()
    return allowed

def is_group_allowed(chat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM allowed_groups WHERE chat_id = ?', (chat_id,))
    allowed = cursor.fetchone() is not None
    conn.close()
    return allowed

# تهيئة قاعدة البيانات
init_db()

# --- لوحة التحكم باستخدام Flask ---
@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    user_stats = get_user_stats()
    welcome_message = get_welcome_message()
    performance = get_bot_performance()
    bot_enabled = is_bot_enabled()
    
    # إحصائيات الأوامر
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM bot_stats')
    stats = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    
    return render_template('panel.html', 
                          user_stats=user_stats, 
                          welcome_message=welcome_message,
                          performance=performance,
                          bot_enabled=bot_enabled,
                          stats=stats)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            log_event('info', 'تم تسجيل الدخول إلى لوحة التحكم')
            return redirect(url_for('index'))
        else:
            log_event('warning', 'محاولة دخول فاشلة')
            return render_template('login.html', error='بيانات الدخول غير صحيحة')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    log_event('info', 'تم تسجيل الخروج من لوحة التحكم')
    return redirect(url_for('login'))

@app.route('/update_welcome', methods=['POST'])
def update_welcome():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    new_message = request.form['welcome_message']
    update_setting('welcome_message', new_message)
    log_event('info', 'تم تحديث رسالة الترحيب')
    return redirect(url_for('index'))

@app.route('/api_settings')
def api_settings():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    apis = get_all_apis()
    return render_template('api_settings.html', apis=apis)

@app.route('/update_api', methods=['POST'])
def update_api():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'غير مسموح'}), 401
    
    api_name = request.form['api_name']
    api_url = request.form['api_url']
    
    update_api_url(api_name, api_url)
    return jsonify({'status': 'success', 'message': 'تم تحديث الـ API بنجاح'})

@app.route('/group_management')
def group_management():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    groups = get_allowed_groups()
    return render_template('group_management.html', groups=groups)

@app.route('/add_group', methods=['POST'])
def add_group():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'غير مسموح'}), 401
    
    chat_id = request.form['chat_id']
    group_name = request.form['group_name']
    added_by = "Admin"
    
    if add_allowed_group(chat_id, group_name, added_by):
        return jsonify({'status': 'success', 'message': 'تمت إضافة المجموعة بنجاح'})
    else:
        return jsonify({'status': 'error', 'message': 'فشل إضافة المجموعة'})

@app.route('/remove_group', methods=['POST'])
def remove_group():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'غير مسموح'}), 401
    
    chat_id = request.form['chat_id']
    if remove_allowed_group(chat_id):
        return jsonify({'status': 'success', 'message': 'تم حذف المجموعة بنجاح'})
    else:
        return jsonify({'status': 'error', 'message': 'فشل حذف المجموعة'})

@app.route('/get_performance')
def get_performance():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'غير مسموح'}), 401
    
    performance = get_bot_performance()
    return jsonify(performance)

@app.route('/toggle_bot', methods=['POST'])
def toggle_bot():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'غير مسموح'}), 401
    
    current_state = is_bot_enabled()
    set_bot_enabled(not current_state)
    log_event('info', f'تم {"تشغيل" if not current_state else "إيقاف"} البوت')
    return jsonify({'status': 'success', 'message': 'تم تغيير حالة البوت', 'new_state': not current_state})

@app.route('/command_settings')
def command_settings():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    commands = [
        {'name': 'like', 'label': 'إرسال إعجابات'},
        {'name': 'visit', 'label': 'إرسال زيارات'},
        {'name': 'info', 'label': 'معلومات اللاعب'},
        {'name': 'check', 'label': 'فحص الحظر'},
        {'name': 'panel', 'label': 'لوحة التحكم'}
    ]
    
    for cmd in commands:
        cmd['enabled'] = is_command_enabled(cmd['name'])
    
    return render_template('command_settings.html', commands=commands)

@app.route('/update_command', methods=['POST'])
def update_command():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'غير مسموح'}), 401
    
    command_name = request.form['command_name']
    enabled = request.form['enabled'] == 'true'
    
    set_command_enabled(command_name, enabled)
    log_event('info', f'تم {"تفعيل" if enabled else "تعطيل"} الأمر: /{command_name}')
    return jsonify({'status': 'success', 'message': 'تم تحديث الإعداد'})

@app.route('/user_management')
def user_management():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    users = get_user_stats()
    return render_template('user_management.html', users=users)

@app.route('/logs')
def view_logs():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    logs = get_logs(100)
    return render_template('logs.html', logs=logs)

@app.route('/team_management')
def team_management():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    team = get_team_members()
    return render_template('team_management.html', team=team)

@app.route('/add_team_member', methods=['POST'])
def add_team_member_endpoint():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'غير مسموح'}), 401
    
    name = request.form['name']
    role = request.form['role']
    telegram = request.form['telegram']
    
    if add_team_member(name, role, telegram):
        return jsonify({'status': 'success', 'message': 'تمت إضافة عضو الفريق بنجاح'})
    else:
        return jsonify({'status': 'error', 'message': 'فشل إضافة عضو الفريق'})

# تشغيل لوحة التحكم في خيط منفصل
def run_panel():
    app.run(host='0.0.0.0', port=PANEL_PORT, use_reloader=False)

threading.Thread(target=run_panel, daemon=True).start()

# --- دوال البوت التلجرام ---
def format_timestamp(ts):
    try:
        return datetime.utcfromtimestamp(int(float(ts))).strftime("%d-%m-%Y %H:%M:%S")
    except:
        return "N/A"

def format_time_delta(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)} ساعة {int(minutes)} دقيقة {int(seconds)} ثانية"

def get_region(uid):
    url = f"{get_api_url('region_api')}?uid={uid}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get('region', 'me')
    except:
        pass
    return 'me'

@bot.message_handler(commands=['start'])
def start(message):
    if not is_bot_enabled():
        return
    
    user = message.from_user
    record_user_usage(str(user.id), user.username, user.first_name, user.last_name)
    
    welcome_msg = get_welcome_message()
    bot.send_message(message.chat.id, welcome_msg, parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=['like'])
def send_like(message):
    if not is_bot_enabled() or not is_command_enabled('like'):
        return
    
    user = message.from_user
    record_user_usage(str(user.id), user.username, user.first_name, user.last_name)
    increment_stat('total_likes')
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ استخدم الأمر هكذا:\n`/like UID`\nمثال: `/like 1234567890`", parse_mode="Markdown")
            return

        uid = parts[1]
        if not uid.isdigit() or len(uid) < 8 or len(uid) > 12:
            bot.send_message(message.chat.id, "❌ يجب أن يكون UID مكون من 8 إلى 12 أرقام فقط!", parse_mode="Markdown")
            return

        wait_msg = bot.send_message(message.chat.id, "⏳ جاري إرسال الإعجابات...")

        # استخدام API الإعجابات الجديد
        url = f"{get_api_url('like_api')}?uid={uid}&server_name=me"
        
        try:
            response = requests.get(url)
            if response.status_code == 200:
                json_data = response.json()
                
                success_message = (
                    "✅ *تم إرسال الإعجابات بنجاح!*\n\n"
                    f"👤 اللاعب: {json_data.get('PlayerNickname', 'N/A')}\n"
                    f"🆔 UID: {json_data.get('UID', uid)}\n"
                    f"🌎 المنطقة: me\n"
                    f"❤️ الإعجابات السابقة: {json_data.get('LikesbeforeCommand', 0)}\n"
                    f"👍 الإعجابات المضافة: {json_data.get('LikesGivenByAPI', 100)}\n"
                    f"❤️ الإجمالي الآن: {json_data.get('LikesafterCommand', 0)}\n\n"
                    "📢 [قناة البوت](https://t.me/FREELIKESBLRX)"
                )
                
                bot.edit_message_text(success_message, chat_id=message.chat.id, 
                                    message_id=wait_msg.message_id, 
                                    parse_mode="Markdown")
                
            else:
                bot.send_message(message.chat.id, f"❌ فشل الطلب. كود الخطأ: {response.status_code}")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ حدث خطأ: {str(e)}")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ غير متوقع في معالجة الطلب")

@bot.message_handler(commands=['visit'])
def send_visit(message):
    if not is_bot_enabled() or not is_command_enabled('visit'):
        return
    
    user = message.from_user
    record_user_usage(str(user.id), user.username, user.first_name, user.last_name)
    increment_stat('total_visits')
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ استخدم الأمر هكذا:\n`/visit UID`\nمثال: `/visit 1234567890`", parse_mode="Markdown")
            return

        uid = parts[1]
        if not uid.isdigit() or len(uid) < 8 or len(uid) > 12:
            bot.send_message(message.chat.id, "❌ يجب أن يكون UID مكون من 8 إلى 12 أرقام فقط!", parse_mode="Markdown")
            return

        wait_msg = bot.send_message(message.chat.id, "⏳ جاري إرسال الزيارات...")

        # استخدام API الزيارات الجديد
        url = f"{get_api_url('visit_api')}/{uid}"
        
        try:
            response = requests.get(url)
            if response.status_code == 200:
                json_data = response.json()
                
                success_message = (
                    "✅ *تم إرسال الزيارات بنجاح!*\n\n"
                    f"👤 اللاعب: {json_data.get('PlayerNickname', 'N/A')}\n"
                    f"🆔 UID: {json_data.get('UID', uid)}\n"
                    f"🌎 المنطقة: me\n"
                    f"👁 الزيارات السابقة: {json_data.get('VisitsbeforeCommand', 0)}\n"
                    f"👣 الزيارات المضافة: {json_data.get('VisitsGivenByAPI', 100)}\n"
                    f"👁 الإجمالي الآن: {json_data.get('VisitsafterCommand', 0)}\n\n"
                    "📢 [قناة البوت](https://t.me/FREELIKESBLRX)"
                )
                
                bot.edit_message_text(success_message, chat_id=message.chat.id, 
                                    message_id=wait_msg.message_id, 
                                    parse_mode="Markdown")
                
            else:
                bot.send_message(message.chat.id, f"❌ فشل الطلب. كود الخطأ: {response.status_code}")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ حدث خطأ: {str(e)}")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ غير متوقع في معالجة الطلب")

@bot.message_handler(commands=['info'])
def player_info(message):
    if not is_bot_enabled() or not is_command_enabled('info'):
        return
    
    user = message.from_user
    record_user_usage(str(user.id), user.username, user.first_name, user.last_name)
    increment_stat('total_info_requests')
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "🎮 *كيف تستخدم الأمر؟*\n`/info UID`\nمثال: `/info 2511293320`", parse_mode="Markdown")
            return

        uid = parts[1]
        if not uid.isdigit() or len(uid) < 8 or len(uid) > 12:
            bot.send_message(message.chat.id, "❌ يجب أن يكون UID مكون من 8 إلى 12 أرقام فقط!", parse_mode="Markdown")
            return

        wait_msg = bot.send_message(message.chat.id, "⏳ جاري البحث عن معلومات اللاعب...")

        # تحديد المنطقة أولاً
        region = get_region(uid)
        
        # استخدام API المعلومات الجديد
        info_url = f"{get_api_url('info_api')}?uid={uid}&region={region}"
        outfit_url = f"{get_api_url('outfit_api')}?uid={uid}&region={region}"

        try:
            info_response = requests.get(info_url)
            if info_response.status_code == 200:
                data = info_response.json()
                player_data = data.get('player_info', {})
                basic_info = player_data.get('basicInfo', {})
                clan_info = player_data.get('clanBasicInfo', {})
                social_info = player_data.get('socialInfo', {})
                
                # استخراج البيانات
                nickname = basic_info.get('nickname', 'N/A')
                level = basic_info.get('level', 'N/A')
                likes = basic_info.get('liked', 'N/A')
                clan_name = clan_info.get('clanName', 'N/A') if clan_info else 'N/A'
                signature = social_info.get('signature', 'N/A').replace('\n', '\n      ')
                
                # الحصول على الرتبة
                rank = basic_info.get('rank', 'N/A')
                max_rank = basic_info.get('maxRank', 'N/A')
                rank_str = f"{rank} (الأعلى: {max_rank})" if max_rank != 'N/A' else rank
                
                # بناء رسالة المعلومات
                info_msg = (
                    "🔰 *معلومات اللاعب* 🔰\n\n"
                    f"👤 الاسم: {nickname}\n"
                    f"🆔 UID: {uid}\n"
                    f"🌎 المنطقة: {region}\n"
                    f"📊 المستوى: {level}\n"
                    f"🏆 الرتبة: {rank_str}\n"
                    f"❤️ الإعجابات: {likes}\n"
                    f"👥 العشيرة: {clan_name}\n"
                    f"📝 البايو: {signature}\n\n"
                    "📢 [BLRXH4RDIXX](https://t.me/BLRXH4RDIXX)"
                )
                
                # إرسال المعلومات النصية أولاً
                try:
                    bot.edit_message_text(info_msg, chat_id=message.chat.id, 
                                        message_id=wait_msg.message_id, 
                                        parse_mode="Markdown")
                except:
                    bot.send_message(message.chat.id, info_msg, parse_mode="Markdown")
                
                # إرسال الزي فقط (لقد تم إزالة البانر)
                try:
                    # إرسال الزي
                    bot.send_photo(
                        chat_id=message.chat.id,
                        photo=outfit_url,
                        caption=f"👕 *زي اللاعب:* {nickname}",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"Error sending outfit image: {e}")
                    bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء جلب صورة الزي", parse_mode="Markdown")
                
            else:
                error_msg = f"❌ فشل جلب المعلومات. كود الخطأ: {info_response.status_code}"
                bot.send_message(message.chat.id, error_msg)
        except Exception as e:
            error_msg = f"❌ حدث خطأ في معالجة البيانات: {str(e)}"
            bot.send_message(message.chat.id, error_msg)
    except Exception as e:
        print(f"Error in player_info: {str(e)}")
        bot.send_message(message.chat.id, "❌ حدث خطأ غير متوقع في معالجة الطلب")

@bot.message_handler(commands=['check'])
def handle_check_command(message):
    if not is_bot_enabled() or not is_command_enabled('check'):
        return
    
    user = message.from_user
    record_user_usage(str(user.id), user.username, user.first_name, user.last_name)
    increment_stat('total_check_requests')
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ استخدم الأمر هكذا:\n`/check UID`\nمثال: `/check 1234567890`", parse_mode="Markdown")
            return

        uid = parts[1]
        if not uid.isdigit() or len(uid) < 8 or len(uid) > 12:
            bot.send_message(message.chat.id, "❌ يجب أن يكون UID مكون من 8 إلى 12 أرقام فقط!", parse_mode="Markdown")
            return
        
        wait_msg = bot.send_message(message.chat.id, f"⏳ جاري التحقق من حالة UID: `{uid}`...", parse_mode="Markdown")

        # التحقق من حالة الحظر
        url = f"{get_api_url('ban_check_api')}?uid={uid}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                ban_info = response.json()
                username = ban_info.get('username', 'N/A')
                
                status_msg = (
                    "🔍 *نتيجة التحقق من الحظر:*\n\n"
                    f"👤 *اللاعب:* `{username}`\n"
                    f"📊 *المستوى:* `{ban_info.get('level', 'N/A')}`\n"
                    f"🌍 *المنطقة:* `{ban_info.get('region', 'N/A')}`\n"
                    f"🔒 *الحالة:* `{ban_info.get('status', 'N/A')}`\n\n"
                    "📢 [BLRXH4RDIXX](https://t.me/BLRXH4RDIXX)"
                )
            else:
                status_msg = (
                    "✅ *هذا اللاعب غير محظور للزيارة*\n\n"
                    f"🆔 *UID:* `{uid}`\n\n"
                    "📢 [BLRXH4RDIXX](https://t.me/BLRXH4RDIXX)"
                )
        except:
            status_msg = (
                "⚠️ *تعذر التحقق من حالة الحظر*\n\n"
                f"🆔 *UID:* `{uid}`\n\n"
                "📢 [BLRXH4RDIXX](https://t.me/BLRXH4RDIXX)"
            )

        try:
            bot.edit_message_text(status_msg, chat_id=message.chat.id, 
                                message_id=wait_msg.message_id, 
                                parse_mode="Markdown")
        except:
            bot.send_message(message.chat.id, status_msg, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ غير متوقع في معالجة الأمر")

@bot.message_handler(commands=['panel'])
def panel_info(message):
    if not is_bot_enabled() or not is_command_enabled('panel'):
        return
    
    user = message.from_user
    record_user_usage(str(user.id), user.username, user.first_name, user.last_name)
    
    panel_url = f"http://your-server-ip:{PANEL_PORT}"
    panel_msg = (
        "🔒 *لوحة تحكم البوت*\n\n"
        "يمكنك الوصول إلى لوحة التحكم عبر الرابط التالي:\n"
        f"{panel_url}\n\n"
        "بيانات الدخول:\n"
        f"👤 اسم المستخدم: `{ADMIN_USERNAME}`\n"
        f"🔑 كلمة المرور: `{ADMIN_PASSWORD}`\n\n"
        "📢 [BLRXH4RDIXX](https://t.me/BLRXH4RDIXX)"
    )
    bot.send_message(message.chat.id, panel_msg, parse_mode="Markdown")

# بدء تشغيل البوت
print("✅ البوت يعمل الآن...")
print(f"🌐 لوحة التحكم تعمل على: http://0.0.0.0:{PANEL_PORT}")
bot.infinity_polling()
