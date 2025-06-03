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

#

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

# ✅ Endpoint: Edit API key (harus ada admin headers)
@app.route('/edit_apikey', methods=['POST'])
def edit_apikey():
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != ADMIN_KEY:
        return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 403

    data = request.get_json()
    apikey = data.get('apikey')
    new_apikey = data.get('new_apikey')
    limitup = data.get('limitup')
    expired = data.get('expired')

    if not all([apikey, new_apikey, limitup, expired]):
        return jsonify({'status': 'error', 'message': 'Missing fields'}), 400

    try:
        datetime.strptime(expired, DATE_FORMAT)
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid date format (dd-mm-yyyy)'}), 400

    key_data = collection.find_one({'apikey': apikey})
    if not key_data:
        return jsonify({'status': 'error', 'message': 'API key not found'}), 404

    # If apikey is changed, check for duplicate
    if apikey != new_apikey and collection.find_one({'apikey': new_apikey}):
        return jsonify({'status': 'error', 'message': 'New API key already exists'}), 409

    collection.update_one(
        {'apikey': apikey},
        {'$set': {'apikey': new_apikey, 'limitup': int(limitup), 'expired': expired}}
    )

    return jsonify({'status': 'success', 'message': 'API key updated'})

# ✅ Endpoint: List semua API key (harus ada admin headers)
@app.route('/list_apikey', methods=['GET'])
def list_apikey():
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != ADMIN_KEY:
        return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 403

    apikeys = []
    for doc in collection.find({}, {'_id': 0}):
        apikeys.append(doc)

    return jsonify({'status': 'success', 'apikeys': apikeys})
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


# ✅ Endpoint: Tambah atau update data dengan parameter pesan dan link (admin only)
@app.route('/add_update', methods=['POST'])
def add_update():
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != ADMIN_KEY:
        return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 403

    data = request.get_json()
    pesan = data.get('pesan')
    link = data.get('link')

    if not all([pesan, link]):
        return jsonify({'status': 'error', 'message': 'Missing fields'}), 400

    # Simpan/update di koleksi baru bernama 'updates'
    updates_col = db["updates"]
    # Hanya satu dokumen, update jika ada, insert jika belum
    updates_col.update_one(
        {},
        {'$set': {'pesan': pesan, 'link': link}},
        upsert=True
    )

    return jsonify({'status': 'success', 'message': 'Update saved'})

# ✅ Endpoint: Cek update, hanya jika apikey valid, tidak expired, dan limit > 0
@app.route('/check_update', methods=['POST'])
def check_update():
    data = request.get_json()
    apikey = data.get('apikey')

    if not apikey:
        return jsonify({'status': 'error', 'message': 'Missing apikey'}), 400

    key_data = collection.find_one({'apikey': apikey})
    if not key_data:
        return jsonify({'status': 'error', 'message': 'API key not found'}), 404

    expired_date = datetime.strptime(key_data['expired'], DATE_FORMAT)
    now = datetime.now()
    if expired_date < now:
        return jsonify({'status': 'error', 'message': 'API key expired'}), 403

    if key_data['limitup'] <= 0:
        return jsonify({'status': 'error', 'message': 'Limit already 0'}), 403

    updates_col = db["updates"]
    update_data = updates_col.find_one({}, {'_id': 0})

    if not update_data:
        return jsonify({'status': 'error', 'message': 'No update found'}), 404

    return jsonify({'status': 'success', 'update': update_data})

# Untuk Vercel deployment
app = app