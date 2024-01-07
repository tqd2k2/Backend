from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from blocklist import BLOCKLIST
from flask_cors import CORS
from flask import request
import cv2
import numpy as np

from func.aes import decrypt
from func.zip import decompress_zlib_data, convert_to_keypoints, convert_to_descriptors
from func.finger import compare_fingerprints
from authlist import auths

blp = Blueprint("Auth", "auth", description="Authenticate")
CORS(blp)

@blp.route("/auth", methods=["POST"])
def post():
    if "file" not in request.files:
        return {"message":"No file attached"}, 400

    file = request.files["file"]

    # Kiểm tra xem file có phải là file ảnh hay không
    if not file.filename.endswith((".jpg", ".jpeg", ".png", ".BMP", ".bmp",".JPG",".JPEG",".PNG")):
        return {"message":"Invalid file format. Only JPG, JPEG, BMP and PNG are supported."}, 400

    # Đọc file ảnh sử dụng OpenCV
    image = cv2.imdecode(np.frombuffer(file.read(), np.uint8), cv2.IMREAD_GRAYSCALE)

    # Tạo đối tượng SIFT
    sift = cv2.SIFT_create()

    # Trích xuất đặc trưng từ ảnh
    uploaded_keypoints, uploaded_descriptors = sift.detectAndCompute(image, None)
    # Lấy dữ liệu qrcode
    qr_code_data = request.form.get("qr_code")
    # Chia dữ liệu
    split_data_parts = qr_code_data.split('.')
    # Giải mã dữ liệu bằng AES
    key = b'\xc2\xe2\xa8B\xf8#\x87\xe5\xe5\x9d\xee\xdc5\t\xf6\xe1/\x9af\x1c\xef\rP1\xce\xe1`\xa1\x89\x83C]'
    iv =b'1234567891234567'
    # Giải mã dữ liệu người dùng
    user_data = decrypt(split_data_parts[0], key, iv)
    user_id = int(user_data.decode('utf-8'))
    # Giải mã dữ liệu finger
    decrypted_data = decrypt(split_data_parts[1], key,iv)
    fingerprint_data  = decompress_zlib_data(decrypted_data)
    stored_keypoints = convert_to_keypoints(fingerprint_data)
    stored_descriptors = convert_to_descriptors(fingerprint_data)
    # So sánh
    match_score = compare_fingerprints(uploaded_keypoints, uploaded_descriptors, stored_keypoints, stored_descriptors)
    # Hiển thị kết quả
    if match_score > 80.0:
        access_token = create_access_token(identity=user_id, fresh=True)
        refresh_token = create_refresh_token(user_id)
        if user_id not in auths:
            auths.append(user_id)
        return {"id": user_id, "match_score": match_score, "access_token": access_token, "refresh_token": refresh_token}, 200
    else:
        return {"message": "Failed!"}, 401

@blp.route("/test")
def test():
    return {"message": "Success!"}, 200

@blp.route("/checkauth")
@jwt_required()
def check():
    current_user = get_jwt_identity()
    if current_user in auths:
        return {"message": "User authenticated."}, 200
    return {"message": "User not authenticate."}, 401