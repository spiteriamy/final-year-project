from flask import Flask, request, jsonify, render_template
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

app = Flask(__name__)

# Load model & tokenizer once at startup
MODEL_PATH = "intent_classifier"
device = "cuda" if torch.cuda.is_available() else "cpu"

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH).to(device)
model.eval()  # set to inference mode

def get_response(user_input):
    # TODO: replace with real response logic
    # return "This is a test response."

    inputs = tokenizer(
        user_input, 
        return_tensors="pt", 
        truncation=True, 
        padding="max_length", 
        max_length=50
    ).to(device)

    with torch.no_grad():
        outputs = model(**inputs)

    probs = torch.softmax(outputs.logits, dim=1)
    prediction = probs.argmax(dim=1).item()
    confidence = probs.max().item()
    label_name = model.config.id2label[prediction]

    return f"Intent: {label_name} ({confidence:.1%})"

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

