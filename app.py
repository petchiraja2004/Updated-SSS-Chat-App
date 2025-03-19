from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, send, disconnect
import os
import re
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*")

user_message_count = {"🧑‍🦱": 0, "👩‍🦰": 0}
blocked_users = set()

# Restricted words list
restricted_words = {"gun", "drug", "bomb", "murder", "terror", "attack"}  # Add more as needed

def delete_message(msg_id, receiver_sid):
    """Deletes the message from the receiver's chat after the set time."""
    socketio.emit("delete_message", {"msg_id": msg_id}, to=receiver_sid)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/user1')
def user1():
    return render_template('user1.html')

@app.route('/user2')
def user2():
    return render_template('user2.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@socketio.on('message')
def handle_message(data):
    global user_message_count, blocked_users
    
    user = data["user"]
    text = data.get("text", "").strip()
    other_user = "👩‍🦰" if user == "🧑‍🦱" else "🧑‍🦱"

    # Extract time limit from message
    duration = None
    time_match = re.search(r"\\t=(\d+)s", text)
    if time_match:
        duration = int(time_match.group(1))
        text = re.sub(r"\\t=\d+s", "", text).strip()  # Remove the time tag from displayed message
    
    # Blocked/unblocked user logic
    if other_user in blocked_users:
        blocked_users.remove(other_user)
        user_message_count[other_user] = 0
        send({"user": "System", "text": f"✅ {other_user} has been unblocked!", "dialog": True}, broadcast=True)
    
    if user in blocked_users:
        send({"user": "System", "text": "⚠ You are blocked due to spamming!", "dialog": True}, to=request.sid)
        return

    # Check for restricted words
    violated = any(word in text.lower() for word in restricted_words)
    if violated:
        send({"user": "System", "text": "⚠ Your message contains restricted words and was NOT sent!", "dialog": True}, to=request.sid)
        return  # Do not send to others

    # Spam detection (Color Coding)
    user_message_count[other_user] = 0  # Reset receiver count
    user_message_count[user] += 1

    if user_message_count[user] == 2:
        data["color"] = "orange"  # Second message → ORANGE
    elif user_message_count[user] == 3:
        data["color"] = "red"  # Third message → RED
        send({"user": "System", "text": f"⚠ {user}, you are suspected of spamming!", "dialog": True}, to=request.sid)
    elif user_message_count[user] > 3:
        blocked_users.add(user)
        send({"user": "System", "text": f"⛔ {user} is blocked due to spamming!", "dialog": True}, broadcast=True)
        disconnect(request.sid)
        return
    else:
        data["color"] = "black"

    data["msg_id"] = f"{user}_{int(time.time())}"  # Unique message ID
    data["receiver"] = other_user  # Identify receiver

    print(f"Received message from {user}: {text} (Consecutive: {user_message_count[user]})")
    send(data, broadcast=True)  # Send message to all clients

    # Schedule deletion if duration is set (Receiver only)
    if duration:
        threading.Thread(target=lambda: (time.sleep(duration), delete_message(data["msg_id"], request.sid)), daemon=True).start()

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return {"error": "No file part"}, 400
    file = request.files['file']
    if file.filename == '':
        return {"error": "No selected file"}, 400
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    file_url = f"/uploads/{file.filename}"
    
    socketio.emit('message', {"user": "System", "text": f"📎 File uploaded: <a href='{file_url}' target='_blank'>{file.filename}</a>"})
    
    return {"file_url": file_url}, 200

if __name__ == '__main__':
    socketio.run(app, debug=True)
