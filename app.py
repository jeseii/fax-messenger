import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fax-secret-key'
app.config['UPLOAD_FOLDER'] = 'uploads'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*")

# Хранилища
users_db = {}  # user_id -> {"username": ..., "online": False}
active_users = {}  # user_id -> {"username": ..., "sid": ...}
private_messages = {}  # user_id -> {other_user_id: [messages]}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    
    user_id = None
    for uid, info in users_db.items():
        if info['username'] == username:
            user_id = uid
            break
    
    if not user_id:
        user_id = str(uuid.uuid4())[:8]
        users_db[user_id] = {"username": username, "online": False}
    
    return jsonify({"user_id": user_id, "username": username})

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

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

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
        
        if user_id not in private_messages:
            private_messages[user_id] = {}
        
        update_users_list()

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
            update_users_list()
            break

def update_users_list():
    users_list = [{"id": uid, "username": info['username'], "online": users_db[uid]['online']} 
                  for uid, info in active_users.items()]
    for uid in users_db:
        if uid not in active_users:
            users_list.append({"id": uid, "username": users_db[uid]['username'], "online": False})
    
    emit('users_online', users_list, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    socketio.run(app, host='0.0.0.0', port=port)