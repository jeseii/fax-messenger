import os
import uuid
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fax-secret-key'
app.config['UPLOAD_FOLDER'] = 'uploads'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*")

# Файлы для хранения данных
USERS_FILE = 'users_data.json'
FRIENDS_FILE = 'friends_data.json'

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(data):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_friends():
    if os.path.exists(FRIENDS_FILE):
        with open(FRIENDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_friends(data):
    with open(FRIENDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Загружаем данные
users_db = load_users()  # user_id -> {"username": ..., "online": False}
friends_db = load_friends()  # user_id -> [friend_ids]
active_users = {}  # user_id -> {"username": ..., "sid": ...}
private_messages = {}

@app.route('/')
def index():
    return render_template('index.html')

# ЕДИНСТВЕННЫЙ маршрут для статики (иконки, manifest.json и т.д.)
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    
    # Проверяем, существует ли пользователь
    user_id = None
    for uid, info in users_db.items():
        if info['username'] == username:
            user_id = uid
            break
    
    if not user_id:
        user_id = str(uuid.uuid4())[:8]
        users_db[user_id] = {"username": username, "online": False}
        save_users(users_db)
    
    return jsonify({"user_id": user_id, "username": username})

@app.route('/api/search_users', methods=['POST'])
def search_users():
    data = request.json
    query = data.get('query', '').lower()
    current_user_id = data.get('user_id')
    
    results = []
    for uid, info in users_db.items():
        if uid != current_user_id and query in info['username'].lower():
            is_friend = uid in friends_db.get(current_user_id, [])
            results.append({
                "id": uid,
                "username": info['username'],
                "online": info.get('online', False),
                "is_friend": is_friend
            })
    return jsonify(results)

@app.route('/api/add_friend', methods=['POST'])
def add_friend():
    data = request.json
    user_id = data.get('user_id')
    friend_id = data.get('friend_id')
    
    if friend_id not in users_db:
        return jsonify({"error": "User not found"}), 404
    
    if user_id not in friends_db:
        friends_db[user_id] = []
    
    if friend_id not in friends_db[user_id]:
        friends_db[user_id].append(friend_id)
        save_friends(friends_db)
        
        # Уведомляем друга (если онлайн)
        if friend_id in active_users:
            socketio.emit('friend_added', {
                "friend_id": user_id,
                "friend_username": users_db[user_id]['username']
            }, to=active_users[friend_id]['sid'])
    
    return jsonify({"success": True})

@app.route('/api/remove_friend', methods=['POST'])
def remove_friend():
    data = request.json
    user_id = data.get('user_id')
    friend_id = data.get('friend_id')
    
    if user_id in friends_db and friend_id in friends_db[user_id]:
        friends_db[user_id].remove(friend_id)
        save_friends(friends_db)
    
    return jsonify({"success": True})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    return jsonify({"url": f"/uploads/{filename}", "name": file.filename})

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('register')
def handle_register(data):
    user_id = data.get('user_id')
    username = data.get('username')
    
    if user_id and user_id in users_db:
        users_db[user_id]['online'] = True
        active_users[user_id] = {"username": username, "sid": request.sid}
        save_users(users_db)
        
        if user_id not in private_messages:
            private_messages[user_id] = {}
        
        update_friends_list(user_id)

@socketio.on('get_friends')
def handle_get_friends():
    user_id = None
    for uid, info in active_users.items():
        if info['sid'] == request.sid:
            user_id = uid
            break
    
    if not user_id:
        return
    
    friends_list = []
    for friend_id in friends_db.get(user_id, []):
        if friend_id in users_db:
            friends_list.append({
                "id": friend_id,
                "username": users_db[friend_id]['username'],
                "online": users_db[friend_id].get('online', False)
            })
    
    emit('friends_list', friends_list)

@socketio.on('get_messages')
def handle_get_messages(data):
    user_id = data.get('user_id')
    other_user_id = data.get('other_user_id')
    
    if user_id in private_messages and other_user_id in private_messages[user_id]:
        emit('messages_history', private_messages[user_id][other_user_id])
    else:
        emit('messages_history', [])

@socketio.on('private_message')
def handle_private_message(data):
    from_user_id = data.get('from_user_id')
    to_user_id = data.get('to_user_id')
    message = data.get('message')
    
    if from_user_id not in users_db or to_user_id not in users_db:
        return
    
    from_username = users_db[from_user_id]['username']
    
    message_data = {
        "id": str(uuid.uuid4())[:8],
        "type": message.get('type', 'text'),
        "content": message.get('content', ''),
        "from": from_username,
        "from_id": from_user_id,
        "timestamp": datetime.now().isoformat(),
        "filename": message.get('name', '')
    }
    
    # Сохраняем для отправителя
    if from_user_id not in private_messages:
        private_messages[from_user_id] = {}
    if to_user_id not in private_messages[from_user_id]:
        private_messages[from_user_id][to_user_id] = []
    private_messages[from_user_id][to_user_id].append(message_data)
    
    # Сохраняем для получателя
    if to_user_id not in private_messages:
        private_messages[to_user_id] = {}
    if from_user_id not in private_messages[to_user_id]:
        private_messages[to_user_id][from_user_id] = []
    private_messages[to_user_id][from_user_id].append(message_data)
    
    # Отправляем получателю (если онлайн)
    if to_user_id in active_users:
        to_sid = active_users[to_user_id]['sid']
        emit('new_private_message', {
            "from_user_id": from_user_id,
            "from_username": from_username,
            "message": message_data
        }, to=to_sid)
    
    # Отправляем отправителю
    emit('new_private_message', {
        "from_user_id": to_user_id,
        "from_username": users_db[to_user_id]['username'],
        "message": message_data
    }, to=request.sid)

@socketio.on('typing_private')
def handle_typing_private(data):
    from_user_id = data.get('from_user_id')
    to_user_id = data.get('to_user_id')
    is_typing = data.get('is_typing', False)
    
    if from_user_id in users_db and to_user_id in active_users:
        to_sid = active_users[to_user_id]['sid']
        emit('user_typing_private', {
            "from_user_id": from_user_id,
            "from_username": users_db[from_user_id]['username'],
            "is_typing": is_typing
        }, to=to_sid)

@socketio.on('disconnect')
def handle_disconnect():
    for user_id, info in list(active_users.items()):
        if info['sid'] == request.sid:
            users_db[user_id]['online'] = False
            del active_users[user_id]
            save_users(users_db)
            
            # Обновляем список друзей у всех, у кого этот пользователь был в друзьях
            for uid in active_users:
                update_friends_list(uid)
            break

def update_friends_list(user_id):
    """Обновляет список друзей для конкретного пользователя"""
    if user_id not in active_users:
        return
    
    friends_list = []
    for friend_id in friends_db.get(user_id, []):
        if friend_id in users_db:
            friends_list.append({
                "id": friend_id,
                "username": users_db[friend_id]['username'],
                "online": users_db[friend_id].get('online', False)
            })
    
    sid = active_users[user_id]['sid']
    emit('friends_list', friends_list, to=sid)

@app.route('/android-icon-192x192.png')
def serve_root_icon():
    return send_from_directory('.', 'android-icon-192x192.png')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    socketio.run(app, host='0.0.0.0', port=port)