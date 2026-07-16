# backend/create_admin.py
import cv2, os, bcrypt
from models import Admin, SessionLocal
from face_utils import encode_face
import face_recognition

print("✅ DB Ready")
print("Enter new admin details\n")

username = input("Username: ").strip()
password = input("Password: ").strip()

# ---------------- Camera capture ----------------
print("\n Starting camera. Press SPACE to capture, ESC to quit.")
# cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cam = cv2.VideoCapture(0)

if not cam.isOpened():
    print("❌ Cannot open camera. Provide image path instead.")
    img_path = input("Enter image path (or 'exit'): ").strip()
    if img_path.lower() == "exit":
        exit()
    if not os.path.exists(img_path):
        print("❌ File not found. Exiting.")
        exit()
    capture_path = img_path
else:
    capture_path = None
    while True:
        ret, frame = cam.read()
        if not ret:
            print("❌ Camera read failed.")
            break

        try:
            cv2.imshow(
                "Admin Capture - SPACE to capture, ESC to cancel",
                frame,
            )
            key = cv2.waitKey(1) & 0xFF
        except Exception:
            # Headless mode → auto capture
            print("⚠ Preview not supported. Capturing automatically.")
            capture_path = "admin_temp.jpg"
            cv2.imwrite(capture_path, frame)
            break

        if key == 27:  # ESC
            print("Cancelled.")
            cam.release()
            try:
                cv2.destroyAllWindows()
            except:
                pass
            exit()

        if key == 32:  # SPACE
            capture_path = "admin_temp.jpg"
            cv2.imwrite(capture_path, frame)
            print("✔ Captured to admin_temp.jpg")
            break

    cam.release()
    try:
        cv2.destroyAllWindows()
    except:
        pass

# ---------------- Detect & Encode face ----------------
try:
    img = cv2.imread(capture_path)
    if img is None:
        raise Exception("Captured image unreadable")

    # Quick check that at least one face exists
    locations = face_recognition.face_locations(img[:, :, ::-1], model="hog")
    if len(locations) == 0:
        print("❌ No face detected in provided image.")
        if capture_path == "admin_temp.jpg" and os.path.exists(capture_path):
            os.remove(capture_path)
        exit()

    print("✔ Face detected")

    enc = encode_face(img)  # BGR numpy → encode_face converts to RGB internally
    print("✔ Face encoded")
except Exception as e:
    print("❌ Error:", e)
    if capture_path == "admin_temp.jpg" and os.path.exists(capture_path):
        os.remove(capture_path)
    exit()

# ---------------- Store admin in DB ----------------
try:
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    with SessionLocal() as db:
        existing = db.query(Admin).filter_by(username=username).first()
        if existing:
            print("❌ Username already exists.")
        else:
            new_admin = Admin(
                username=username,
                password_hash=hashed,
                face_encoding=enc.tobytes(),
            )
            db.add(new_admin)
            db.commit()
            print("\n🎉 ADMIN CREATED SUCCESSFULLY!")
            print(" Username:", username)
            print(" Face Encoding Stored ✔")
except Exception as e:
    print("❌ DB error:", e)

# ---------------- Cleanup ----------------
if capture_path == "admin_temp.jpg" and os.path.exists(capture_path):
    os.remove(capture_path)
