from flask import Flask, jsonify, request, make_response
from database_connection import connect_to_neo4j  # Hàm kết nối tới Neo4j
from etherscan_to_neo4j import fetch_and_save_transactions  # Hàm xử lý giao dịch từ Etherscan
from dotenv import load_dotenv
import os
import time
from flask_cors import CORS

# Load các biến môi trường từ .envS
load_dotenv()

# Khởi tạo Flask app
app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*"}})

# Kết nối với Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://aadff3f9.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

try:
    neo4j_driver = connect_to_neo4j(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    print("Connected to Neo4j successfully!")
except Exception as e:
    print(f"Failed to connect to Neo4j: {e}")

# Middleware thêm tiêu đề CORS
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

@app.route('/', methods=['GET'])
def home():
    """Root route to verify API is running."""
    return jsonify({"message": "API is running!"})

@app.route('/api/transactions', methods=['GET', 'OPTIONS'])
def get_transactions():
    """Fetch transactions for a given address."""
    if request.method == 'OPTIONS':
        # Phản hồi preflight request
        response = make_response(jsonify({"message": "Preflight request successful"}))
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response
    start_time = time.time()  # Bắt đầu theo dõi thời gian xử lý

    try:
        address = request.args.get('address')
        if not address:
            return jsonify({"error": "Address is required"}), 400

        # Fetch transaction data and save to Neo4j
        transactions = fetch_and_save_transactions(address)
        processing_time = time.time() - start_time  # Kết thúc theo dõi
        print(f"Processed {len(transactions)} transactions for address {address} in {processing_time:.2f} seconds")

        # Return transactions as JSON response
        return jsonify({"success": True, "transactions": transactions}), 200

    except Exception as e:
        # Xử lý lỗi nếu xảy ra
        print(f"Error processing request for address {address}: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)  # Local development port
