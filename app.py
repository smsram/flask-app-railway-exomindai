from flask import Flask, request, jsonify, redirect, url_for
from flask_cors import CORS
import mysql.connector
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

db_config = {
    'host': 'gateway01.ap-southeast-1.prod.aws.tidbcloud.com',
    'user': '3xBx9XutyPAhozK.root',
    'password': 'm9n6KheQVxc92qYi',
    'database': 'authentication'
}

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data['username']
    email = data['email']
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    # Check if the username or email already exists
    cursor.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
    existing_user = cursor.fetchone()
    
    if existing_user:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Username or email already exists'})
    
    # Proceed with signup if username or email does not exist
    name = data.get('name', '')
    phone = data.get('phone', '')
    password = data['password']
    
    cursor.execute("INSERT INTO users (username, name, phone, email, password) VALUES (%s, %s, %s, %s, %s)", 
                   (username, name, phone, email, password))
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data['username']
    password = data['password']
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    cursor.execute("SELECT username FROM users WHERE username = %s AND password = %s", (username, password))
    result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if result:
        return jsonify({'success': True, 'username': result[0], 'redirect_url': 'index.html'})
    else:
        return jsonify({'success': False, 'message': 'Invalid username or password'})

@app.route('/get-name', methods=['GET'])
def get_name():
    username = request.args.get('username')

    if not username:
        return jsonify({'success': False, 'message': 'No username provided'})

    try:
        # Connect to TiDB
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Fetch the user's name from the database
        cursor.execute("SELECT name FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if result and result[0]:  # Check if name exists
            return jsonify({'success': True, 'name': result[0]})
        else:
            return jsonify({'success': False, 'message': 'Name not found'})
    except Exception as e:
        print(f"Error fetching user name: {e}")
        return jsonify({'success': False, 'message': 'Error fetching user name'})

@app.route('/get-profile-image', methods=['GET'])
def get_profile_image():
    username = request.args.get('username')

    if not username:
        return jsonify({'success': False, 'message': 'No username provided'})

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        cursor.execute("SELECT profile_image_url FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if result and result[0]:  # Check if profile_image_url exists
            return jsonify({'success': True, 'profile_image_url': result[0]})
        else:
            return jsonify({'success': False, 'message': 'Profile image not found'})
    except Exception as e:
        print(f"Error fetching profile image: {e}")
        return jsonify({'success': False, 'message': 'Error fetching profile image'})

@app.route('/update-profile-image', methods=['POST'])
def update_profile_image():
    data = request.get_json()
    username = data['username']
    new_profile_image_url = data['profile_image_url']
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    cursor.execute("UPDATE users SET profile_image_url = %s WHERE username = %s", (new_profile_image_url, username))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({'success': True, 'message': 'Profile image updated successfully'})

@app.route('/save-message', methods=['POST'])
def save_message():
    data = request.get_json()
    username = data.get('username')
    message = data.get('message')
    sender = data.get('sender')  # 'user' or 'bot'

    if not username or not message or not sender:
        return jsonify({'success': False, 'message': 'Invalid data provided'})

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Find the user ID based on the username
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user_result = cursor.fetchone()

        if user_result:
            user_id = user_result[0]

            # Fetch and clear all results for the chat query
            cursor.execute("SELECT chat_id FROM chats WHERE user_id = %s", (user_id,))
            chat_result = cursor.fetchone()
            
            if cursor.rowcount > 0:
                cursor.fetchall()  # Ensure no unread results remain
            
            # If no chat exists, create a new one
            if not chat_result:
                cursor.execute("INSERT INTO chats (chat_name, user_id) VALUES (%s, %s)", (f"{username}'s Chat", user_id))
                conn.commit()
                chat_id = cursor.lastrowid
            else:
                chat_id = chat_result[0]

            # Insert the message into the messages table
            cursor.execute("INSERT INTO messages (chat_id, sender, message_text) VALUES (%s, %s, %s)",
                           (chat_id, sender, message))
            conn.commit()
            response = {'success': True}
        else:
            response = {'success': False, 'message': 'User not found'}

        cursor.close()
        conn.close()
        return jsonify(response)

    except mysql.connector.Error as e:
        print(f"MySQL Error saving message: {e}")
        return jsonify({'success': False, 'message': 'Database error'})

    except Exception as e:
        print(f"Error saving message: {e}")
        return jsonify({'success': False, 'message': 'Error saving message'})

@app.route('/get-messages', methods=['GET'])
def get_messages():
    username = request.args.get('username')
    if not username:
        return jsonify({'success': False, 'message': 'Username not provided'})

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)  # Return results as dictionaries

        # Fetch all messages for the user
        query = """
            SELECT m.message_text, m.sender, m.sent_at 
            FROM messages m 
            JOIN chats c ON m.chat_id = c.chat_id 
            JOIN users u ON c.user_id = u.id 
            WHERE u.username = %s 
            ORDER BY m.sent_at ASC
        """
        cursor.execute(query, (username,))
        messages = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'messages': messages})

    except mysql.connector.Error as e:
        print(f"MySQL Error fetching messages: {e}")
        return jsonify({'success': False, 'message': 'Database error'})

    except Exception as e:
        print(f"Error fetching messages: {e}")
        return jsonify({'success': False, 'message': 'Error fetching messages'})

@app.route('/delete-messages', methods=['DELETE'])
def delete_messages():
    username = request.args.get('username')
    if not username:
        return jsonify({'success': False, 'message': 'Username not provided'})

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Find the user ID based on the username
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user_result = cursor.fetchone()

        if user_result:
            user_id = user_result[0]

            # Delete messages associated with the user's chat
            cursor.execute("""
                DELETE m FROM messages m
                JOIN chats c ON m.chat_id = c.chat_id
                WHERE c.user_id = %s
            """, (user_id,))
            conn.commit()

            response = {'success': True, 'message': 'Messages deleted successfully'}
        else:
            response = {'success': False, 'message': 'User not found'}

        cursor.close()
        conn.close()
        return jsonify(response)

    except mysql.connector.Error as e:
        print(f"MySQL Error deleting messages: {e}")
        return jsonify({'success': False, 'message': 'Database error'})

    except Exception as e:
        print(f"Error deleting messages: {e}")
        return jsonify({'success': False, 'message': 'Error deleting messages'})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
