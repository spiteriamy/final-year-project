from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

def get_response(user_input):
    # TODO: replace with real response logic
    return "This is a test response."

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Empty message"}), 400
    
    bot_reply = get_response(user_message)
    return jsonify({"response": bot_reply})

if __name__ == "__main__":
    app.run(debug=True)

