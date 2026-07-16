import cv2
import numpy as np
import face_recognition
import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("face_utils")

# Lower = more strict. 0.45 is fairly strict for security.
SIMILARITY_THRESHOLD = 0.45


# ---------------------------------------
# Validate image before using it
# ---------------------------------------
def _validate_image(img):
    if img is None:
        raise ValueError("Image is None")

    if not isinstance(img, np.ndarray):
        raise ValueError("Image is not a numpy array")

    if img.size == 0:
        raise ValueError("Image array is empty")

    if len(img.shape) != 3 or img.shape[2] != 3:
        raise ValueError(f"Invalid image shape: {img.shape}")

    return True


# ---------------------------------------
# Extract face encoding (128-D dlib vector)
# ---------------------------------------
def encode_face(img_or_path):
    # Path input
    if isinstance(img_or_path, str):
        img = face_recognition.load_image_file(img_or_path)  # RGB
        if img is None or img.size == 0:
            raise ValueError("Failed to load image file")
    else:
        # numpy → validate
        _validate_image(img_or_path)

        # convert BGR → RGB
        try:
            img = cv2.cvtColor(img_or_path, cv2.COLOR_BGR2RGB)
        except Exception:
            raise ValueError("Failed to convert BGR→RGB")

    # Detect face
    locations = face_recognition.face_locations(img, model="hog")
    if len(locations) == 0:
        raise ValueError("No face detected in image")

    # Compute embedding
    encs = face_recognition.face_encodings(img, known_face_locations=locations)
    if not encs:
        raise ValueError("Failed to compute face encoding")

    return encs[0].astype(np.float32)


# ---------------------------------------
# Convert DB bytes → float vector
# ---------------------------------------
def decode_embedding(raw_bytes):
    if raw_bytes is None:
        return np.array([], dtype=np.float32)
    return np.frombuffer(raw_bytes, dtype=np.float32)


# ---------------------------------------
# Compare faces (Euclidean)
# ---------------------------------------
def compare_faces(known_bytes, test_img):
    """
    known_bytes: bytes from DB (Admin.face_encoding / Voter.face_encoding)
    test_img   : numpy BGR image (from OpenCV) OR path
    """
    known = decode_embedding(known_bytes)

    if known.size == 0:
        logger.warning("compare_faces: known embedding empty")
        return False

    try:
        new_emb = encode_face(test_img)
    except Exception as e:
        logger.warning(f"compare_faces: could not encode test image: {e}")
        return False

    if known.size != new_emb.size:
        logger.warning(
            f"compare_faces: embedding size mismatch {known.size} vs {new_emb.size}"
        )
        return False

    dist = float(np.linalg.norm(known - new_emb))
    logger.info(f"[FaceMatch] distance = {dist:.4f}")

    return dist <= SIMILARITY_THRESHOLD


# ---------------------------------------
# Face encoding → SHA256 hash for blockchain
# ---------------------------------------
def hash_encoding(emb):
    return "0x" + hashlib.sha256(emb.tobytes()).hexdigest()
