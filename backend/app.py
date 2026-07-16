# backend/app.py

import base64
import datetime
import json
import os
from functools import wraps

import bcrypt
import cv2
import jwt
import numpy as np

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

from flask import Flask, g, jsonify, redirect, request, send_from_directory
from flask_cors import CORS
from web3 import Web3

from config.secret import (
    ABI_PATH,
    ADMIN_ACCOUNT,
    ADMIN_PRIVATE_KEY,
    CONTRACT_ADDRESS,
    JWT_SECRET,
    RPC_URL,
)
from face_utils import compare_faces, encode_face, hash_encoding
from models import Admin, SessionLocal, Voter


# ================================================================
# APPLICATION PATHS
# ================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
SESSION_FILE = os.path.join(BASE_DIR, "voting_session.json")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__, static_folder=FRONTEND_PATH, static_url_path="")
CORS(app)


# ================================================================
# BLOCKCHAIN SETUP
# ================================================================

w3 = Web3(Web3.HTTPProvider(RPC_URL))

if not w3.is_connected():
    raise RuntimeError(f"Could not connect to Ganache at {RPC_URL}")

with open(ABI_PATH, "r", encoding="utf-8") as abi_file:
    contract_json = json.load(abi_file)

abi = contract_json if isinstance(contract_json, list) else contract_json.get("abi")
if not abi:
    raise ValueError(f"No ABI found in {ABI_PATH}")

admin_account = Web3.to_checksum_address(ADMIN_ACCOUNT)
contract_address = Web3.to_checksum_address(CONTRACT_ADDRESS)

contract = w3.eth.contract(address=contract_address, abi=abi)

print(f"Blockchain connected: {w3.is_connected()}")
print(f"Contract address: {contract_address}")


# ================================================================
# VOTING SESSION HELPERS
# ================================================================

def load_session():
    """Load the locally configured voting session."""
    if not os.path.exists(SESSION_FILE):
        return {"start": None, "end": None}

    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as session_file:
            data = json.load(session_file)
            return {
                "start": data.get("start"),
                "end": data.get("end"),
            }
    except (OSError, json.JSONDecodeError):
        return {"start": None, "end": None}


def save_session(start_iso, end_iso):
    """Save the voting session to a local JSON file."""
    with open(SESSION_FILE, "w", encoding="utf-8") as session_file:
        json.dump({"start": start_iso, "end": end_iso}, session_file, indent=2)


def get_voting_status():
    """Return the current local voting-session status."""
    session = load_session()
    start_iso = session.get("start")
    end_iso = session.get("end")

    if not start_iso or not end_iso:
        return {
            "status": "not_set",
            "start": None,
            "end": None,
            "remaining_seconds": 0,
            "opens_in_seconds": 0,
        }

    try:
        start = datetime.datetime.fromisoformat(start_iso)
        end = datetime.datetime.fromisoformat(end_iso)
    except ValueError:
        return {
            "status": "not_set",
            "start": None,
            "end": None,
            "remaining_seconds": 0,
            "opens_in_seconds": 0,
        }

    now = datetime.datetime.now()

    if now < start:
        return {
            "status": "upcoming",
            "start": start_iso,
            "end": end_iso,
            "remaining_seconds": 0,
            "opens_in_seconds": max(0, int((start - now).total_seconds())),
        }

    if now <= end:
        return {
            "status": "open",
            "start": start_iso,
            "end": end_iso,
            "remaining_seconds": max(0, int((end - now).total_seconds())),
            "opens_in_seconds": 0,
        }

    return {
        "status": "closed",
        "start": start_iso,
        "end": end_iso,
        "remaining_seconds": 0,
        "opens_in_seconds": 0,
    }


# ================================================================
# GENERAL HELPERS
# ================================================================

def get_bytes(value):
    """Convert a database binary value to normal bytes."""
    if value is None:
        return b""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    return bytes(value)


def save_image_b64(data_url, destination):
    """Decode a Base64 image, save it temporarily, and return its OpenCV image."""
    if not data_url:
        raise ValueError("Image is required")

    encoded = data_url.split(",", 1)[1] if "," in data_url else data_url

    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid Base64 image") from exc

    image_array = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Invalid image data")

    if not cv2.imwrite(destination, image):
        raise OSError("Could not save temporary image")

    return image


def safe_delete(path):
    """Delete a temporary file without masking the original error."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def blockchain_error_message(error):
    """Extract a readable Ganache/Web3 error message."""
    if not error.args:
        return str(error)

    details = error.args[0]
    if not isinstance(details, dict):
        return str(details)

    data = details.get("data")
    if isinstance(data, dict):
        return (
            data.get("reason")
            or data.get("message")
            or details.get("message")
            or "Blockchain transaction failed"
        )

    return details.get("message") or "Blockchain transaction failed"


def send_contract_tx(function, *args, gas=350_000):
    """Sign, send, and confirm a smart-contract transaction."""
    try:
        nonce = w3.eth.get_transaction_count(admin_account, "pending")

        transaction = function(*args).build_transaction(
            {
                "from": admin_account,
                "nonce": nonce,
                "gas": gas,
                "gasPrice": w3.to_wei("1", "gwei"),
                "chainId": w3.eth.chain_id,
            }
        )

        signed = w3.eth.account.sign_transaction(
            transaction,
            private_key=ADMIN_PRIVATE_KEY,
        )

        raw_transaction = getattr(
            signed,
            "raw_transaction",
            getattr(signed, "rawTransaction", None),
        )
        if raw_transaction is None:
            raise RuntimeError("Could not access the signed raw transaction")

        transaction_hash = w3.eth.send_raw_transaction(raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(transaction_hash, timeout=120)

        if receipt.status != 1:
            return None, "Blockchain transaction was reverted"

        return transaction_hash.hex(), None

    except ValueError as error:
        return None, blockchain_error_message(error)
    except Exception as error:
        return None, str(error)


# ================================================================
# AUTHENTICATION
# ================================================================

def admin_required(route_function):
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return jsonify({"error": "Token missing"}), 401

        token = authorization.removeprefix("Bearer ").strip()

        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            username = payload.get("username")

            if not username:
                return jsonify({"error": "Invalid token"}), 401

            with SessionLocal() as database:
                admin = database.query(Admin).filter_by(username=username).first()
                if not admin:
                    return jsonify({"error": "Admin not found"}), 401
                g.admin_username = admin.username

        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return route_function(*args, **kwargs)

    return wrapper


# ================================================================
# FRONTEND ROUTES
# ================================================================

@app.route("/")
def landing():
    return send_from_directory(FRONTEND_PATH, "home.html")


@app.route("/voter")
def voter_page():
    return send_from_directory(FRONTEND_PATH, "voters.html")


@app.route("/admin")
def admin_page():
    return send_from_directory(FRONTEND_PATH, "admin_login.html")


@app.route("/admin-dashboard")
def admin_dashboard():
    token = request.args.get("token", "")
    try:
        jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return redirect("/admin?expired=1")

    return send_from_directory(FRONTEND_PATH, "admin.html")


@app.route("/candidate")
def candidate_page():
    return send_from_directory(FRONTEND_PATH, "candidate.html")


@app.route("/register-voter")
def register_voter_page():
    token = request.args.get("token", "")
    try:
        jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return redirect("/admin?expired=1")

    return send_from_directory(FRONTEND_PATH, "register_voter.html")


@app.route("/results")
def results_page():
    return send_from_directory(FRONTEND_PATH, "results.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_PATH, filename)


# ================================================================
# VOTING SESSION API
# ================================================================

@app.route("/voting_status", methods=["GET"])
def voting_status():
    return jsonify(get_voting_status())


@app.route("/admin/set_voting_session", methods=["POST"])
@admin_required
def set_voting_session():
    data = request.get_json(silent=True) or {}
    start_iso = data.get("start")
    end_iso = data.get("end")

    if not start_iso or not end_iso:
        return jsonify({"error": "Start and end are required"}), 400

    try:
        start = datetime.datetime.fromisoformat(start_iso)
        end = datetime.datetime.fromisoformat(end_iso)
    except ValueError:
        return jsonify({"error": "Use ISO format: YYYY-MM-DDTHH:MM:SS"}), 400

    if end <= start:
        return jsonify({"error": "End time must be after start time"}), 400

    save_session(start_iso, end_iso)
    return jsonify({"ok": True, "start": start_iso, "end": end_iso})


@app.route("/admin/clear_voting_session", methods=["POST"])
@admin_required
def clear_voting_session():
    save_session(None, None)
    return jsonify({"ok": True})


# ================================================================
# ADMIN API
# ================================================================

@app.route("/admin/login_step1", methods=["POST"])
def admin_login_step1():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    with SessionLocal() as database:
        admin = database.query(Admin).filter_by(username=username).first()

        if not admin:
            return jsonify({"error": "Invalid username"}), 401

        if not bcrypt.checkpw(password.encode(), admin.password_hash.encode()):
            return jsonify({"error": "Wrong password"}), 401

    return jsonify({"ok": True})


@app.route("/admin/login_face", methods=["POST"])
def admin_login_face():
    username = (request.form.get("username") or "").strip()
    image_b64 = request.form.get("image")

    if not username or not image_b64:
        return jsonify({"error": "Username and image are required"}), 400

    with SessionLocal() as database:
        admin = database.query(Admin).filter_by(username=username).first()
        if not admin:
            return jsonify({"error": "Unknown admin"}), 404
        known_face = get_bytes(admin.face_encoding)

    temporary_path = os.path.join(UPLOAD_FOLDER, f"admin_{username}.jpg")

    try:
        image = save_image_b64(image_b64, temporary_path)

        if not compare_faces(known_face, image):
            return jsonify({"error": "Face mismatch"}), 401

        token = jwt.encode(
            {
                "username": username,
                "exp": datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(hours=4),
            },
            JWT_SECRET,
            algorithm="HS256",
        )
        return jsonify({"ok": True, "token": token})

    except Exception as error:
        return jsonify({"error": "Face login failed", "detail": str(error)}), 500
    finally:
        safe_delete(temporary_path)


@app.route("/admin/add_candidate", methods=["POST"])
@admin_required
def add_candidate():
    if get_voting_status()["status"] == "open":
        return jsonify(
            {"error": "Cannot add candidates during an active voting session"}
        ), 403

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or request.form.get("name") or "").strip()

    if not name:
        return jsonify({"error": "Candidate name is required"}), 400

    transaction_hash, error = send_contract_tx(
        contract.functions.addCandidate,
        name,
        gas=300_000,
    )

    if error:
        return jsonify({"error": error}), 500

    return jsonify({"ok": True, "tx": transaction_hash})


@app.route("/admin/voters", methods=["GET"])
@admin_required
def voters_list():
    with SessionLocal() as database:
        voters = database.query(Voter).all()
        return jsonify(
            [
                {
                    "id": voter.id,
                    "enrollment": voter.enrollment,
                    "name": voter.name,
                }
                for voter in voters
            ]
        )


@app.route("/admin/delete_voter/<int:voter_id>", methods=["DELETE"])
@admin_required
def delete_voter(voter_id):
    if get_voting_status()["status"] == "open":
        return jsonify(
            {"error": "Cannot delete voters during an active voting session"}
        ), 403

    with SessionLocal() as database:
        voter = database.query(Voter).filter_by(id=voter_id).first()
        if not voter:
            return jsonify({"error": "Voter not found"}), 404

        try:
            database.delete(voter)
            database.commit()
            return jsonify({"ok": True})
        except Exception as error:
            database.rollback()
            return jsonify({"error": str(error)}), 500


@app.route("/admin/register_voter_camera", methods=["POST"])
@admin_required
def register_voter_camera():
    if get_voting_status()["status"] == "open":
        return jsonify(
            {"error": "Cannot register voters during an active voting session"}
        ), 403

    enrollment = (request.form.get("enrollment") or "").strip()
    name = (request.form.get("name") or "").strip()
    image_b64 = request.form.get("image")

    if not enrollment or not name or not image_b64:
        return jsonify({"error": "All fields are required"}), 400

    temporary_path = os.path.join(UPLOAD_FOLDER, f"temp_{enrollment}.jpg")

    with SessionLocal() as database:
        if database.query(Voter).filter_by(enrollment=enrollment).first():
            return jsonify({"error": "Enrollment already registered"}), 409

        try:
            image = save_image_b64(image_b64, temporary_path)
            new_encoding = encode_face(image)

            for existing_voter in database.query(Voter).all():
                if compare_faces(get_bytes(existing_voter.face_encoding), image):
                    return jsonify({"error": "This face is already registered"}), 409

            face_hash = hash_encoding(new_encoding)
            face_hash_bytes32 = Web3.to_bytes(hexstr=face_hash)

            transaction_hash, error = send_contract_tx(
                contract.functions.registerVoter,
                enrollment,
                face_hash_bytes32,
            )
            if error:
                return jsonify({"error": error}), 500

            database.add(
                Voter(
                    enrollment=enrollment,
                    name=name,
                    face_encoding=new_encoding.tobytes(),
                )
            )
            database.commit()

            return jsonify({"ok": True, "tx": transaction_hash})

        except Exception as error:
            database.rollback()
            return jsonify({"error": str(error)}), 500
        finally:
            safe_delete(temporary_path)


# ================================================================
# PUBLIC VOTING API
# ================================================================

@app.route("/vote", methods=["POST"])
def cast_vote():
    voting_session = get_voting_status()

    if voting_session["status"] == "not_set":
        return jsonify({"error": "Voting session is not configured"}), 403
    if voting_session["status"] == "upcoming":
        return jsonify({"error": "Voting has not started yet"}), 403
    if voting_session["status"] == "closed":
        return jsonify({"error": "Voting session has ended"}), 403

    enrollment = (request.form.get("enrollment") or "").strip()
    candidate_id = request.form.get("candidate_id")
    image_b64 = request.form.get("image")

    if not enrollment or not candidate_id or not image_b64:
        return jsonify({"error": "All fields are required"}), 400

    try:
        candidate_id = int(candidate_id)
    except ValueError:
        return jsonify({"error": "Invalid candidate"}), 400

    temporary_path = os.path.join(UPLOAD_FOLDER, f"{enrollment}_vote.jpg")

    with SessionLocal() as database:
        voter = database.query(Voter).filter_by(enrollment=enrollment).first()
        if not voter:
            return jsonify({"error": "Voter not found"}), 404

        known_face = get_bytes(voter.face_encoding)

    try:
        image = save_image_b64(image_b64, temporary_path)

        if not compare_faces(known_face, image):
            return jsonify({"error": "Face mismatch"}), 401

        new_encoding = encode_face(image)
        face_hash = hash_encoding(new_encoding)
        face_hash_bytes32 = Web3.to_bytes(hexstr=face_hash)

        transaction_hash, error = send_contract_tx(
            contract.functions.vote,
            enrollment,
            face_hash_bytes32,
            candidate_id,
        )

        if error:
            lowered_error = error.lower()
            if "already voted" in lowered_error or "face already used" in lowered_error:
                return jsonify({"error": "You have already voted"}), 400
            if "invalid candidate" in lowered_error:
                return jsonify({"error": "Invalid candidate"}), 400
            return jsonify({"error": error}), 500

        return jsonify({"ok": True, "tx": transaction_hash})

    except Exception as error:
        return jsonify({"error": "Vote failed", "detail": str(error)}), 500
    finally:
        safe_delete(temporary_path)


@app.route("/candidates", methods=["GET"])
def candidates_list():
    try:
        total = contract.functions.candidateCount().call()
        candidates = []

        for candidate_id in range(1, total + 1):
            stored_id, name, vote_count = (
                contract.functions.getCandidate(candidate_id).call()
            )
            candidates.append(
                {
                    "id": stored_id,
                    "name": name,
                    "votes": vote_count,
                }
            )

        return jsonify(candidates)

    except Exception as error:
        return jsonify({"error": "Could not load candidates", "detail": str(error)}), 500


# NOTE:
# The current ManageElection Solidity contract does not define deleteCandidate().
# Therefore, the broken /admin/delete_candidate route was intentionally removed.


# ================================================================
# RUN
# ================================================================

if __name__ == "__main__":
    print("\nServer running at http://127.0.0.1:5000\n")
    app.run(debug=True)