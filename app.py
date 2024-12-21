from flask import Flask, render_template, request, redirect, url_for, session
import firebase_admin
from firebase_admin import credentials, db
import face_recognition
import os
import numpy as np
import base64

app = Flask(__name__)
app.secret_key = "your_secret_key"

cred = credentials.Certificate("face-attendence-system-fe8cb-firebase-adminsdk-4g2w9-450fd4f05c.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://face-attendence-system-fe8cb-default-rtdb.asia-southeast1.firebasedatabase.app'
})

users_ref = db.reference('users')
votes_ref = db.reference('votes')

def encode_face(image_path):
    image = face_recognition.load_image_file(image_path)
    encodings = face_recognition.face_encodings(image)
    if encodings:
        return encodings[0].tolist() 
    else:
        return None

def is_face_match(input_encoding, stored_encoding):
    return face_recognition.compare_faces([np.array(stored_encoding)], np.array(input_encoding))[0]

@app.route("/", methods=["GET", "POST"])
def login():
    error_message = None
    if request.method == "POST":
        image_data = request.form.get("image")
        if image_data:
            header, encoded = image_data.split(",", 1)
            binary_data = base64.b64decode(encoded)
            temp_path = "temp.jpg"
            with open(temp_path, "wb") as temp_file:
                temp_file.write(binary_data)

            input_encoding = encode_face(temp_path)
            os.remove(temp_path) 

            if input_encoding:
                users = users_ref.get() or {}
                for user_id, user_data in users.items():
                    if is_face_match(input_encoding, user_data['face_encoding']):
                        session['user_id'] = user_id
                        session['role'] = user_data['role']

                        if user_data['role'] == 'admin':
                            return redirect(url_for("admin_panel"))
                        elif user_data['role'] == 'user':
                            return redirect(url_for("user"))

                error_message = "Invalid user! Face not recognized."
            else:
                error_message = "Could not detect a face in the image. Please try again."
        else:
            error_message = "No image data received. Please try again."

    return render_template("login.html", error_message=error_message)

@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    message = None
    if request.method == "POST":
        action = request.form.get("action")
        user_id = request.form.get("user_id")

        if action == "delete" and user_id:
            users_ref.child(user_id).delete()
            message = "User deleted successfully."
        elif action == "edit" and user_id:
            new_role = request.form.get("new_role")
            if new_role in ["admin", "user"]:
                users_ref.child(user_id).update({"role": new_role})
                message = "User role updated successfully."
        else:
            name = request.form.get("name")
            role = request.form.get("role")
            image_data = request.form.get("image")

            if name and role in ["admin", "user"] and image_data:
                header, encoded = image_data.split(",", 1)
                binary_data = base64.b64decode(encoded)
                temp_path = "temp.jpg"
                with open(temp_path, "wb") as temp_file:
                    temp_file.write(binary_data)

                face_encoding = encode_face(temp_path)
                os.remove(temp_path)  

                if face_encoding:
                    users_ref.push({
                        "name": name,
                        "role": role,
                        "face_encoding": face_encoding,
                        "has_voted": False
                    })
                    message = f"{role.capitalize()} '{name}' added successfully."
                else:
                    message = "No face detected in the uploaded image."
            else:
                message = "Invalid input. Ensure all fields are filled correctly."

    users = users_ref.get() or {}
    votes = votes_ref.get() or {}
    return render_template("admin.html", users=users, votes=votes, message=message)

@app.route("/create_vote", methods=["POST"])
def create_vote():
    vote_name = request.form.get("vote_name")
    candidate_names = request.form.getlist("candidate_name[]")
    candidate_parties = request.form.getlist("candidate_party[]")

    if not vote_name or not candidate_names or not candidate_parties:
        return redirect(url_for("admin_panel", message="All fields are required!"))

    candidates = []
    for i in range(len(candidate_names)):
        candidates.append({
            "name": candidate_names[i],
            "party": candidate_parties[i],
            "votes": 0
        })

    votes_ref.push({
        "vote_name": vote_name,
        "candidates": candidates
    })

    return redirect(url_for("admin_panel", message=f"Vote '{vote_name}' created successfully!"))

# Route: User Page
@app.route("/user")
def user():
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect(url_for("login"))

    user_id = session['user_id']
    user = users_ref.child(user_id).get()
    votes = votes_ref.get() or {}

    if not isinstance(user.get('has_voted'), dict):
        users_ref.child(user_id).update({'has_voted': {}})
        user['has_voted'] = {}

    return render_template("user.html", votes=votes, has_voted=user['has_voted'])


@app.route("/cast_vote", methods=["POST"])
def cast_vote():
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect(url_for("login"))

    user_id = session['user_id']
    vote_id = request.form.get("vote_id")
    candidate_name = request.form.get("candidate_name")
    image_data = request.form.get("image")

    if not vote_id or not candidate_name or not image_data:
        return redirect(url_for("user"))

    header, encoded = image_data.split(",", 1)
    binary_data = base64.b64decode(encoded)
    temp_path = "temp_vote.jpg"
    with open(temp_path, "wb") as temp_file:
        temp_file.write(binary_data)

    input_encoding = encode_face(temp_path)
    os.remove(temp_path)  

    if not input_encoding:
        return render_template(
            "user.html",
            votes=votes_ref.get(),
            has_voted=users_ref.child(user_id).child("has_voted").get() or {},
            error="Face not recognized. Please try again."
        )

    user = users_ref.child(user_id).get()

    if not is_face_match(input_encoding, user["face_encoding"]):
        return render_template(
            "user.html",
            votes=votes_ref.get(),
            has_voted=users_ref.child(user_id).child("has_voted").get() or {},
            error="Face does not match. Voting is not allowed."
        )

    if not isinstance(user.get("has_voted"), dict):
        users_ref.child(user_id).update({"has_voted": {}})
        user["has_voted"] = {}

    if user["has_voted"].get(vote_id, False):
        return render_template(
            "user.html",
            votes=votes_ref.get(),
            has_voted=user["has_voted"],
            error=f"You have already voted in '{vote_id}'."
        )

    vote = votes_ref.child(vote_id).get()
    if not vote:
        return redirect(url_for("user"))

    for candidate in vote["candidates"]:
        if candidate["name"] == candidate_name:
            candidate["votes"] += 1

    votes_ref.child(vote_id).update({"candidates": vote["candidates"]})

    users_ref.child(user_id).child("has_voted").update({vote_id: True})

    return redirect(url_for("user"))

@app.route("/delete_vote", methods=["POST"])
def delete_vote():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for("login"))

    vote_id = request.form.get("vote_id")
    if vote_id:
        votes_ref.child(vote_id).delete()
        message = "Vote deleted successfully."
    else:
        message = "Invalid vote ID."

    users = users_ref.get() or {}
    votes = votes_ref.get() or {}
    return render_template("admin.html", users=users, votes=votes, message=message)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
