from flask import Flask, request, jsonify
from datetime import datetime
from pymongo import MongoClient, errors
import os

app = Flask(__name__)

# ✅ MongoDB Atlas connection (pakai URL dari kamu)
MONGO_URL = os.environ.get("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["apikey_database"]
collection = db["apikeys"]

# ✅ Buat koleksi dan index unik jika belum ada
if "apikeys" not in db.list_collection_names():
    db.create_collection("apikeys")
collection.create_index("apikey", unique=True)

# ✅ Admin API Key (digunakan di headers 'X-Admin-Key')
ADMIN_KEY = "secret_admin_key"
DATE_FORMAT = "%d-%m-%Y"

# ✅ Endpoint: Tambah API key (harus ada admin headers)
@app.route('/add_apikey', methods=['POST'])
def add_apikey():
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != ADMIN_KEY:
        return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 403

    data = request.get_json()
    apikey = data.get('apikey')
    limitup = data.get('limitup')
    expired = data.get('expired')

    if not all([apikey, limitup, expired]):
        return jsonify({'status': 'error', 'message': 'Missing fields'}), 400

    try:
        datetime.strptime(expired, DATE_FORMAT)
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid date format (dd-mm-yyyy)'}), 400

    try:
        collection.insert_one({
            'apikey': apikey,
            'limitup': int(limitup),
            'expired': expired
        })
    except errors.DuplicateKeyError:
        return jsonify({'status': 'error', 'message': 'API key already exists'}), 409

    return jsonify({'status': 'success', 'message': 'API key added'})

# ✅ Endpoint: Cek API key
@app.route('/check_apikey', methods=['POST'])
def check_apikey():
    data = request.get_json()
    apikey = data.get('apikey')

    key_data = collection.find_one({'apikey': apikey})
    if not key_data:
        return jsonify({'status': 'error', 'message': 'API key not found'}), 404

    expired_date = datetime.strptime(key_data['expired'], DATE_FORMAT)
    now = datetime.now()
    status_msg = 'expired apikey' if expired_date < now else 'active apikey'

    return jsonify({
        'apikey': apikey,
        'expired': key_data['expired'],
        'limitup': key_data['limitup'],
        'message': status_msg
    })

# ✅ Endpoint: Kurangi 1 limit berdasarkan apikey
@app.route('/update_limit', methods=['POST'])
def update_limit():
    data = request.get_json()
    apikey = data.get('apikey')

    key_data = collection.find_one({'apikey': apikey})
    if not key_data:
        return jsonify({'status': 'error', 'message': 'API key not found'}), 404

    if key_data['limitup'] <= 0:
        return jsonify({'status': 'error', 'message': 'Limit already 0'}), 403

    new_limit = key_data['limitup'] - 1
    collection.update_one({'apikey': apikey}, {'$set': {'limitup': new_limit}})

    return jsonify({
        'status': 'success',
        'message': 'Limit reduced by 1',
        'limitup': new_limit
    })

# Untuk Vercel deployment
app = app