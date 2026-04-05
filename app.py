import os
import uuid
import json
import traceback
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fax-secret-key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('avatars', exist_ok=True)
os.makedirs('stickers', exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/api/test', methods=['GET'])
def test_api():
    return jsonify({"status": "ok", "message": "API is working"})

USERS_FILE = 'users_data.json'
FRIENDS_FILE = 'friends_data.json'
MESSAGES_FILE = 'messages_data.json'
DRAFTS_FILE = 'drafts_data.json'
GROUPS_FILE = 'groups_data.json'
STICKERS_FILE = 'stickers_data.json'

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

def load_messages():
    if os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_messages(data):
    with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_drafts():
    if os.path.exists(DRAFTS_FILE):
        with open(DRAFTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_drafts(data):
    with open(DRAFTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_groups():
    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_groups(data):
    with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_stickers():
    if os.path.exists(STICKERS_FILE):
        with open(STICKERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_stickers(data):
    with open(STICKERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

users_db = load_users()
friends_db = load_friends()
private_messages = load_messages()
drafts = load_drafts()
groups_db = load_groups()
stickers_db = load_stickers()
active_users = {}
unread_counts = {}

@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    user_id = request.form.get('user_id')
    if not user_id:
        return jsonify({"error": "No user_id"}), 400
    ext = file.filename.split('.')[-1] if '.' in file.filename else 'png'
    filename = f"{user_id}.{ext}"
    filepath = os.path.join('avatars', filename)
    file.save(filepath)
    avatar_url = f"/avatars/{filename}"
    if user_id in users_db:
        users_db[user_id]['avatar'] = avatar_url
        save_users(users_db)
    return jsonify({"url": avatar_url})

@app.route('/avatars/<filename>')
def serve_avatar(filename):
    return send_from_directory('avatars', filename)

@app.route('/upload_sticker', methods=['POST'])
def upload_sticker():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    sticker_id = str(uuid.uuid4())[:8]
    ext = file.filename.split('.')[-1] if '.' in file.filename else 'png'
    filename = f"{sticker_id}.{ext}"
    filepath = os.path.join('stickers', filename)
    file.save(filepath)
    sticker_url = f"/stickers/{filename}"
    stickers_db[sticker_id] = {"url": sticker_url, "created_at": datetime.now().isoformat()}
    save_stickers(stickers_db)
    return jsonify({"id": sticker_id, "url": sticker_url})

@app.route('/stickers/<filename>')
def serve_sticker(filename):
    return send_from_directory('stickers', filename)

@app.route('/api/get_stickers', methods=['GET'])
def get_stickers():
    return jsonify(list(stickers_db.values()))

@app.route('/api/get_friends_for_group', methods=['POST'])
def get_friends_for_group():
    data = request.json
    user_id = data.get('user_id')
    friends_list = []
    for friend_id in friends_db.get(user_id, []):
        if friend_id in users_db:
            friends_list.append({
                "id": friend_id,
                "username": users_db[friend_id]['username'],
                "avatar": users_db[friend_id].get('avatar')
            })
    return jsonify(friends_list)

@app.route('/api/create_group', methods=['POST'])
def create_group():
    try:
        data = request.json
        print("Received:", data)
        return jsonify({
            "id": "test123",
            "name": data.get('name', 'Test'),
            "creator": data.get('creator_id'),
            "members": [data.get('creator_id')] + data.get('members', []),
            "is_group": True
        })
    except Exception as e:
        print("Error:", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/add_to_group', methods=['POST'])
def add_to_group():
    data = request.json
    group_id = data.get('group_id')
    user_id = data.get('user_id')
    new_member_id = data.get('new_member_id')
    if group_id not in groups_db:
        return jsonify({"error": "Group not found"}), 404
    if user_id != groups_db[group_id]['creator']:
        return jsonify({"error": "Only creator can add members"}), 403
    if new_member_id not in groups_db[group_id]['members']:
        groups_db[group_id]['members'].append(new_member_id)
        save_groups(groups_db)
        if group_id not in private_messages:
            private_messages[group_id] = {}
        if new_member_id not in private_messages:
            private_messages[new_member_id] = {}
        if group_id not in private_messages[new_member_id]:
            private_messages[new_member_id][group_id] = []
        if new_member_id not in private_messages[group_id]:
            private_messages[group_id][new_member_id] = []
        save_messages(private_messages)
        if new_member_id in active_users:
            try:
                socketio.emit('group_updated', {"group": groups_db[group_id]}, to=active_users[new_member_id]['sid'])
                update_groups_list(new_member_id)
            except Exception as e:
                print(f"Error emitting group_updated: {e}")
    return jsonify(groups_db[group_id])

@app.route('/api/leave_group', methods=['POST'])
def leave_group():
    data = request.json
    group_id = data.get('group_id')
    user_id = data.get('user_id')
    if group_id not in groups_db:
        return jsonify({"error": "Group not found"}), 404
    if user_id in groups_db[group_id]['members']:
        groups_db[group_id]['members'].remove(user_id)
        if len(groups_db[group_id]['members']) == 0:
            del groups_db[group_id]
        else:
            save_groups(groups_db)
    return jsonify({"success": True})

@app.route('/api/get_groups', methods=['POST'])
def get_groups():
    data = request.json
    user_id = data.get('user_id')
    user_groups = []
    for gid, group in groups_db.items():
        if user_id in group['members']:
            user_groups.append(group)
    return jsonify(user_groups)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/.well-known/assetlinks.json')
def serve_assetlinks():
    return send_from_directory('.well-known', 'assetlinks.json')

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
                "avatar": info.get('avatar'),
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
        if friend_id in active_users:
            try:
                socketio.emit('friend_added', {
                    "friend_id": user_id,
                    "friend_username": users_db[user_id]['username']
                }, to=active_users[friend_id]['sid'])
            except Exception as e:
                print(f"Error emitting friend_added: {e}")
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

@app.route('/api/search_messages', methods=['POST'])
def search_messages():
    data = request.json
    user_id = data.get('user_id')
    chat_id = data.get('chat_id')
    query = data.get('query', '').lower()
    results = []
    if user_id in private_messages and chat_id in private_messages[user_id]:
        for msg in private_messages[user_id][chat_id]:
            if msg.get('type') == 'text' and query in msg.get('content', '').lower():
                results.append(msg)
    return jsonify(results)

@app.route('/api/save_draft', methods=['POST'])
def save_draft():
    data = request.json
    user_id = data.get('user_id')
    chat_id = data.get('chat_id')
    draft_text = data.get('draft', '')
    if user_id not in drafts:
        drafts[user_id] = {}
    drafts[user_id][chat_id] = draft_text
    save_drafts(drafts)
    return jsonify({"success": True})

@app.route('/api/get_draft', methods=['POST'])
def get_draft():
    data = request.json
    user_id = data.get('user_id')
    chat_id = data.get('chat_id')
    draft = drafts.get(user_id, {}).get(chat_id, '')
    return jsonify({"draft": draft})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    original_filename = secure_filename(file.filename)
    ext = original_filename.split('.')[-1] if '.' in original_filename else 'bin'
    new_filename = f"{datetime.now().timestamp()}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
    file.save(filepath)
    file_url = f"/uploads/{new_filename}"
    return jsonify({"url": file_url, "name": original_filename})

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
        save_users(users_db)
        if user_id not in private_messages:
            private_messages[user_id] = {}
        if user_id not in unread_counts:
            unread_counts[user_id] = {}
        update_friends_list(user_id)
        update_groups_list(user_id)

@socketio.on('mark_as_read')
def handle_mark_as_read(data):
    user_id = data.get('user_id')
    chat_id = data.get('chat_id')
    if user_id in unread_counts:
        unread_counts[user_id][chat_id] = 0
    if chat_id in active_users:
        try:
            emit('messages_read', {"by": user_id, "chat_with": chat_id}, to=active_users[chat_id]['sid'])
        except Exception as e:
            print(f"Error emitting messages_read: {e}")
    if user_id in private_messages and chat_id in private_messages[user_id]:
        for msg in private_messages[user_id][chat_id]:
            if msg['from_id'] == chat_id and msg.get('status') != 'read':
                msg['status'] = 'read'
    if chat_id in private_messages and user_id in private_messages[chat_id]:
        for msg in private_messages[chat_id][user_id]:
            if msg['from_id'] == user_id and msg.get('status') != 'read':
                msg['status'] = 'read'
    save_messages(private_messages)

@socketio.on('edit_message')
def handle_edit_message(data):
    message_id = data.get('message_id')
    new_content = data.get('new_content')
    user_id = data.get('user_id')
    chat_id = data.get('chat_id')
    for msg in private_messages.get(user_id, {}).get(chat_id, []):
        if msg['id'] == message_id and msg['from_id'] == user_id:
            msg['content'] = new_content
            msg['edited'] = True
            break
    for msg in private_messages.get(chat_id, {}).get(user_id, []):
        if msg['id'] == message_id and msg['from_id'] == user_id:
            msg['content'] = new_content
            msg['edited'] = True
            break
    save_messages(private_messages)
    if user_id in active_users:
        try:
            emit('message_edited', {"message_id": message_id, "new_content": new_content}, to=active_users[user_id]['sid'])
        except Exception as e:
            print(f"Error emitting message_edited: {e}")
    if chat_id in active_users:
        try:
            emit('message_edited', {"message_id": message_id, "new_content": new_content}, to=active_users[chat_id]['sid'])
        except Exception as e:
            print(f"Error emitting message_edited: {e}")

@socketio.on('delete_message')
def handle_delete_message(data):
    message_id = data.get('message_id')
    user_id = data.get('user_id')
    chat_id = data.get('chat_id')
    if user_id in private_messages and chat_id in private_messages[user_id]:
        private_messages[user_id][chat_id] = [msg for msg in private_messages[user_id][chat_id] if msg['id'] != message_id]
    if chat_id in private_messages and user_id in private_messages[chat_id]:
        private_messages[chat_id][user_id] = [msg for msg in private_messages[chat_id][user_id] if msg['id'] != message_id]
    save_messages(private_messages)
    if user_id in active_users:
        try:
            emit('message_deleted', {"message_id": message_id}, to=active_users[user_id]['sid'])
        except Exception as e:
            print(f"Error emitting message_deleted: {e}")
    if chat_id in active_users:
        try:
            emit('message_deleted', {"message_id": message_id}, to=active_users[chat_id]['sid'])
        except Exception as e:
            print(f"Error emitting message_deleted: {e}")

@socketio.on('forward_message')
def handle_forward_message(data):
    from_user_id = data.get('from_user_id')
    to_chat_id = data.get('to_chat_id')
    original_message = data.get('message')
    if from_user_id not in users_db:
        return
    from_username = users_db[from_user_id]['username']
    is_group = to_chat_id in groups_db
    chat_name = groups_db[to_chat_id]['name'] if is_group else users_db.get(to_chat_id, {}).get('username', '')
    forwarded_message = {
        "id": str(uuid.uuid4())[:8],
        "type": original_message.get('type', 'text'),
        "content": original_message.get('content', ''),
        "from": from_username,
        "from_id": from_user_id,
        "timestamp": datetime.now().isoformat(),
        "filename": original_message.get('filename', ''),
        "is_forwarded": True,
        "original_from": original_message.get('from', from_username),
        "chat_name": chat_name,
        "is_group": is_group
    }
    if from_user_id not in private_messages:
        private_messages[from_user_id] = {}
    if to_chat_id not in private_messages[from_user_id]:
        private_messages[from_user_id][to_chat_id] = []
    private_messages[from_user_id][to_chat_id].append(forwarded_message)
    if to_chat_id not in private_messages:
        private_messages[to_chat_id] = {}
    if from_user_id not in private_messages[to_chat_id]:
        private_messages[to_chat_id][from_user_id] = []
    private_messages[to_chat_id][from_user_id].append(forwarded_message)
    if to_chat_id not in unread_counts:
        unread_counts[to_chat_id] = {}
    unread_counts[to_chat_id][from_user_id] = unread_counts[to_chat_id].get(from_user_id, 0) + 1
    save_messages(private_messages)
    if is_group:
        for member_id in groups_db[to_chat_id]['members']:
            if member_id in active_users and member_id != from_user_id:
                try:
                    emit('new_private_message', {
                        "from_user_id": from_user_id,
                        "from_username": from_username,
                        "message": forwarded_message,
                        "is_group": True,
                        "group_name": groups_db[to_chat_id]['name']
                    }, to=active_users[member_id]['sid'])
                except Exception as e:
                    print(f"Error emitting new_private_message: {e}")
    else:
        if to_chat_id in active_users:
            try:
                emit('new_private_message', {
                    "from_user_id": from_user_id,
                    "from_username": from_username,
                    "message": forwarded_message
                }, to=active_users[to_chat_id]['sid'])
            except Exception as e:
                print(f"Error emitting new_private_message: {e}")
    try:
        emit('new_private_message', {
            "from_user_id": to_chat_id,
            "from_username": chat_name,
            "message": forwarded_message
        }, to=request.sid)
    except Exception as e:
        print(f"Error emitting new_private_message to self: {e}")
    update_friends_list(from_user_id)

@socketio.on('reply_message')
def handle_reply_message(data):
    from_user_id = data.get('from_user_id')
    to_chat_id = data.get('to_chat_id')
    message = data.get('message')
    reply_to = data.get('reply_to')
    if from_user_id not in users_db:
        return
    from_username = users_db[from_user_id]['username']
    is_group = to_chat_id in groups_db
    chat_name = groups_db[to_chat_id]['name'] if is_group else users_db.get(to_chat_id, {}).get('username', '')
    message_data = {
        "id": str(uuid.uuid4())[:8],
        "type": message.get('type', 'text'),
        "content": message.get('content', ''),
        "from": from_username,
        "from_id": from_user_id,
        "timestamp": datetime.now().isoformat(),
        "filename": message.get('name', ''),
        "status": "sent",
        "reply_to": reply_to,
        "is_group": is_group,
        "chat_name": chat_name
    }
    if from_user_id not in private_messages:
        private_messages[from_user_id] = {}
    if to_chat_id not in private_messages[from_user_id]:
        private_messages[from_user_id][to_chat_id] = []
    private_messages[from_user_id][to_chat_id].append(message_data)
    if to_chat_id not in private_messages:
        private_messages[to_chat_id] = {}
    if from_user_id not in private_messages[to_chat_id]:
        private_messages[to_chat_id][from_user_id] = []
    private_messages[to_chat_id][from_user_id].append(message_data)
    if to_chat_id not in unread_counts:
        unread_counts[to_chat_id] = {}
    unread_counts[to_chat_id][from_user_id] = unread_counts[to_chat_id].get(from_user_id, 0) + 1
    save_messages(private_messages)
    if is_group:
        for member_id in groups_db[to_chat_id]['members']:
            if member_id in active_users and member_id != from_user_id:
                try:
                    emit('new_private_message', {
                        "from_user_id": from_user_id,
                        "from_username": from_username,
                        "message": message_data,
                        "is_group": True,
                        "group_name": groups_db[to_chat_id]['name']
                    }, to=active_users[member_id]['sid'])
                except Exception as e:
                    print(f"Error emitting new_private_message: {e}")
    else:
        if to_chat_id in active_users:
            try:
                emit('new_private_message', {
                    "from_user_id": from_user_id,
                    "from_username": from_username,
                    "message": message_data
                }, to=active_users[to_chat_id]['sid'])
            except Exception as e:
                print(f"Error emitting new_private_message: {e}")
    try:
        emit('new_private_message', {
            "from_user_id": to_chat_id,
            "from_username": chat_name,
            "message": message_data
        }, to=request.sid)
    except Exception as e:
        print(f"Error emitting new_private_message to self: {e}")
    update_friends_list(from_user_id)

@socketio.on('add_reaction')
def handle_add_reaction(data):
    message_id = data.get('message_id')
    reaction = data.get('reaction')
    user_id = data.get('user_id')
    chat_id = data.get('chat_id')
    for msg in private_messages.get(user_id, {}).get(chat_id, []):
        if msg['id'] == message_id:
            if 'reactions' not in msg:
                msg['reactions'] = {}
            msg['reactions'][user_id] = reaction
            break
    for msg in private_messages.get(chat_id, {}).get(user_id, []):
        if msg['id'] == message_id:
            if 'reactions' not in msg:
                msg['reactions'] = {}
            msg['reactions'][user_id] = reaction
            break
    save_messages(private_messages)
    if user_id in active_users:
        try:
            emit('reaction_added', {"message_id": message_id, "reaction": reaction, "by": user_id}, to=active_users[user_id]['sid'])
        except Exception as e:
            print(f"Error emitting reaction_added: {e}")
    if chat_id in active_users:
        try:
            emit('reaction_added', {"message_id": message_id, "reaction": reaction, "by": user_id}, to=active_users[chat_id]['sid'])
        except Exception as e:
            print(f"Error emitting reaction_added: {e}")

@socketio.on('join_group')
def handle_join_group(data):
    user_id = data.get('user_id')
    group_id = data.get('group_id')
    if group_id in groups_db and user_id in groups_db[group_id]['members']:
        if user_id not in private_messages:
            private_messages[user_id] = {}
        if group_id not in private_messages[user_id]:
            private_messages[user_id][group_id] = []
        try:
            emit('group_history', private_messages[user_id].get(group_id, []), to=request.sid)
        except Exception as e:
            print(f"Error emitting group_history: {e}")

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
                "online": users_db[friend_id].get('online', False),
                "avatar": users_db[friend_id].get('avatar'),
                "unread": unread_counts.get(user_id, {}).get(friend_id, 0)
            })
    try:
        emit('friends_list', friends_list, to=request.sid)
    except Exception as e:
        print(f"Error emitting friends_list: {e}")

@socketio.on('get_messages')
def handle_get_messages(data):
    user_id = data.get('user_id')
    chat_id = data.get('chat_id')
    if user_id in unread_counts:
        unread_counts[user_id][chat_id] = 0
    if user_id in private_messages and chat_id in private_messages[user_id]:
        try:
            emit('messages_history', private_messages[user_id][chat_id], to=request.sid)
        except Exception as e:
            print(f"Error emitting messages_history: {e}")
    else:
        try:
            emit('messages_history', [], to=request.sid)
        except Exception as e:
            print(f"Error emitting messages_history: {e}")

@socketio.on('private_message')
def handle_private_message(data):
    from_user_id = data.get('from_user_id')
    to_chat_id = data.get('to_chat_id')
    message = data.get('message')
    if from_user_id not in users_db:
        return
    from_username = users_db[from_user_id]['username']
    is_group = to_chat_id in groups_db
    chat_name = groups_db[to_chat_id]['name'] if is_group else users_db.get(to_chat_id, {}).get('username', '')
    message_data = {
        "id": str(uuid.uuid4())[:8],
        "type": message.get('type', 'text'),
        "content": message.get('content', ''),
        "from": from_username,
        "from_id": from_user_id,
        "timestamp": datetime.now().isoformat(),
        "filename": message.get('name', ''),
        "status": "sent",
        "is_group": is_group,
        "chat_name": chat_name
    }
    if message.get('reply_to'):
        message_data['reply_to'] = message['reply_to']
    if from_user_id not in private_messages:
        private_messages[from_user_id] = {}
    if to_chat_id not in private_messages[from_user_id]:
        private_messages[from_user_id][to_chat_id] = []
    private_messages[from_user_id][to_chat_id].append(message_data)
    if to_chat_id not in private_messages:
        private_messages[to_chat_id] = {}
    if from_user_id not in private_messages[to_chat_id]:
        private_messages[to_chat_id][from_user_id] = []
    private_messages[to_chat_id][from_user_id].append(message_data)
    if to_chat_id not in unread_counts:
        unread_counts[to_chat_id] = {}
    unread_counts[to_chat_id][from_user_id] = unread_counts[to_chat_id].get(from_user_id, 0) + 1
    save_messages(private_messages)
    if is_group:
        for member_id in groups_db[to_chat_id]['members']:
            if member_id in active_users and member_id != from_user_id:
                try:
                    emit('new_private_message', {
                        "from_user_id": from_user_id,
                        "from_username": from_username,
                        "message": message_data,
                        "is_group": True,
                        "group_name": groups_db[to_chat_id]['name']
                    }, to=active_users[member_id]['sid'])
                except Exception as e:
                    print(f"Error emitting new_private_message: {e}")
    else:
        if to_chat_id in active_users:
            try:
                emit('new_private_message', {
                    "from_user_id": from_user_id,
                    "from_username": from_username,
                    "message": message_data
                }, to=active_users[to_chat_id]['sid'])
            except Exception as e:
                print(f"Error emitting new_private_message: {e}")
    try:
        emit('new_private_message', {
            "from_user_id": to_chat_id,
            "from_username": chat_name,
            "message": message_data
        }, to=request.sid)
    except Exception as e:
        print(f"Error emitting new_private_message to self: {e}")
    update_friends_list(from_user_id)
    update_groups_list(from_user_id)

@socketio.on('typing_private')
def handle_typing_private(data):
    from_user_id = data.get('from_user_id')
    to_chat_id = data.get('to_chat_id')
    is_typing = data.get('is_typing', False)
    if from_user_id not in users_db:
        return
    is_group = to_chat_id in groups_db
    if is_group:
        for member_id in groups_db[to_chat_id]['members']:
            if member_id in active_users and member_id != from_user_id:
                try:
                    emit('user_typing_private', {
                        "from_user_id": from_user_id,
                        "from_username": users_db[from_user_id]['username'],
                        "is_typing": is_typing,
                        "is_group": True,
                        "group_name": groups_db[to_chat_id]['name']
                    }, to=active_users[member_id]['sid'])
                except Exception as e:
                    print(f"Error emitting user_typing_private: {e}")
    else:
        if to_chat_id in active_users:
            try:
                emit('user_typing_private', {
                    "from_user_id": from_user_id,
                    "from_username": users_db[from_user_id]['username'],
                    "is_typing": is_typing
                }, to=active_users[to_chat_id]['sid'])
            except Exception as e:
                print(f"Error emitting user_typing_private: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    for user_id, info in list(active_users.items()):
        if info['sid'] == request.sid:
            users_db[user_id]['online'] = False
            del active_users[user_id]
            save_users(users_db)
            for uid in active_users:
                update_friends_list(uid)
            break

def update_friends_list(user_id):
    if user_id not in active_users:
        return
    friends_list = []
    for friend_id in friends_db.get(user_id, []):
        if friend_id in users_db:
            friends_list.append({
                "id": friend_id,
                "username": users_db[friend_id]['username'],
                "online": users_db[friend_id].get('online', False),
                "avatar": users_db[friend_id].get('avatar'),
                "unread": unread_counts.get(user_id, {}).get(friend_id, 0)
            })
    sid = active_users[user_id]['sid']
    try:
        emit('friends_list', friends_list, to=sid)
    except Exception as e:
        print(f"Error emitting friends_list in update: {e}")

def update_groups_list(user_id):
    if user_id not in active_users:
        return
    groups_list = []
    for gid, group in groups_db.items():
        if user_id in group['members']:
            groups_list.append(group)
    sid = active_users[user_id]['sid']
    try:
        emit('groups_list', groups_list, to=sid)
    except Exception as e:
        print(f"Error emitting groups_list: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    socketio.run(app, host='0.0.0.0', port=port)
