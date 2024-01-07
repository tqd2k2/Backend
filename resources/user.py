from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    get_jwt,
    jwt_required,
)
from passlib.hash import pbkdf2_sha256
import os
from models import UserModel
from schemas import UserSchema
from blocklist import BLOCKLIST
from authlist import auths
from flask_cors import CORS

blp = Blueprint("Users", "users", description="Operations on users")
CORS(blp)

@blp.route("/register")
class UserRegister(MethodView):
    @blp.arguments(UserSchema)
    def post(self, user_data):
        if UserModel.find_by_username(user_data["username"]):
            abort(400, message="A user with that username already exists.")

        user = UserModel(
            username=user_data["username"],
            password=pbkdf2_sha256.hash(user_data["password"]),
        )
        user.save_to_db()

        return {"message": "User created successfully.","user_id": user.id}, 201


@blp.route("/login")
class UserLogin(MethodView):
    @blp.arguments(UserSchema)
    def post(self, user_data):
        user = UserModel.find_by_username(user_data["username"])

        if user and pbkdf2_sha256.verify(user_data["password"], user.password):
            access_token = create_access_token(identity=user.id, fresh=True)
            refresh_token = create_refresh_token(user.id)
            return {"access_token": access_token, "refresh_token": refresh_token}, 200

        abort(401, message="Invalid credentials.")


@blp.route("/logout")
class UserLogout(MethodView):
    @jwt_required()
    def post(self):
        jti = get_jwt()["jti"]
        BLOCKLIST.add(jti)
        current_user = get_jwt_identity()
        for n in auths:
            if n == current_user:
                auths.remove(n)
        return {"message": "Successfully logged out"}, 200


@blp.route("/user/<int:user_id>")
class User(MethodView):
    @jwt_required()
    @blp.response(200, UserSchema)
    def get(self, user_id):
        current_user = get_jwt_identity()
        if current_user not in auths:
            abort(401, message="User not authenticate.")
        user = UserModel.find_by_id(user_id)
        if not user:
            abort(404, message="User not found.")
        return user


    def delete(self, user_id):
        user = UserModel.find_by_id(user_id)
        if not user:
            abort(404, message="User not found.")
        user.delete_from_db()
        folder_path = f"uploads/{user_id}"
        file_path = f"uploads/{user_id}/qrcode_{user_id}.png"
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                os.rmdir(folder_path)
                return {"message": "User deleted."}, 204
            except Exception as e:
                return {"message": f"Failed to delete SQRC and directory: {str(e)}"}, 500
        else:
            return {"message": "Directory not found"}, 404


@blp.route("/refresh")
class TokenRefresh(MethodView):
    @jwt_required(refresh=True)
    def post(self):
        current_user = get_jwt_identity()
        new_token = create_access_token(identity=current_user, fresh=False)
        return {"access_token": new_token}, 200

@blp.route("/user")
class UserList(MethodView):
    @jwt_required()
    @blp.response(200, UserSchema(many=True))
    def get(self):
        current_user = get_jwt_identity()
        if current_user not in auths:
            abort(401, message="User not authenticate.")
        if not get_jwt()["is_admin"]:
            abort(401, message="Admin privilege required.")
        return UserModel.query.all()