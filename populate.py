import firebase_admin
from firebase_admin import credentials, db
import face_recognition
import os

cred = credentials.Certificate("face-attendence-system-fe8cb-firebase-adminsdk-4g2w9-450fd4f05c.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://face-attendence-system-fe8cb-default-rtdb.asia-southeast1.firebasedatabase.app'
})



users_ref = db.reference('users')

def encode_face(image_path):
    image = face_recognition.load_image_file(image_path)
    encodings = face_recognition.face_encodings(image)
    if encodings:
        return encodings[0].tolist() 
    else:
        return None

def add_user(name, role, image_path):
    if role not in ["admin", "user"]:
        print("Invalid role. Choose either 'admin' or 'user'.")
        return

    if not os.path.exists(image_path):
        print(f"Image file '{image_path}' does not exist.")
        return

    print(f"Encoding face for {name}...")
    face_encoding = encode_face(image_path)

    if face_encoding:
        users_ref.push({
            "name": name,
            "role": role,
            "face_encoding": face_encoding,
            "has_voted": False
        })
        print(f"{role.capitalize()} '{name}' added successfully.")
    else:
        print("No face detected in the image. Please try another image.")

if __name__ == "__main__":
    while True:
        print("\n--- Add User or Admin ---")
        name = input("Enter name: ")
        role = input("Enter role (admin/user): ").strip().lower()
        image_path = input("Enter path to image: ").strip()

        add_user(name, role, image_path)

        another = input("Do you want to add another? (yes/no): ").strip().lower()
        if another != "yes":
            break
