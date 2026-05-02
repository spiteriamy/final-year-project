from flask import Flask, request, jsonify, render_template
import os
from model_definitions.inference import MorphologicalAnalyserService, IntentClassifierService
import re
from nltk.corpus import words
import json
import sqlite3
from database import init_db
from datetime import datetime
from pathlib import Path


app = Flask(__name__)

# initialise database
DB_PATH = Path("survey_responses.db")
init_db(DB_PATH)  # run once at import time

# Load response templates once at startup
with open("response_templates.json", "r", encoding="utf-8") as f:
    RESPONSE_TEMPLATES = json.load(f)

# Map intent labels -> morphology feature keys
INTENT_TO_FEATURE = {
    "part_of_speech": "pos",
    "person": "person",
    "mood":   "mood",
    "tense":  "tense",
    "voice":  "voice",
    "number": "number",
    "case":   "case",
    "gender": "gender",
    # aspect / declension / conjugation: not produced by the analyser yet
}

# Load models once at startup

print("Loading models...")

intent_classifier = IntentClassifierService(model_path=os.path.join("saved_models", "intent_classifier"))


my_thresholds = {
    "pos": 0.879,
    "person": 0.969,
    "number": 0.929,
    "tense": 0.889,
    "mood": 0.964,
    "voice": 0.949 ,
    "gender": 0.934 ,
    "case": 0.959 ,
    "degree": 0.873,
}

morphological_analyser = MorphologicalAnalyserService(
    model_path=os.path.join("saved_models", "morphological_analyser"),
    bert_path=os.path.join("saved_models", "latin_bert"),
    thresholds=my_thresholds
)


ENGLISH_VOCAB = set(w.lower() for w in words.words())

def tokenize(sentence: str) -> list[str]:
    """Split on whitespace and remove punctuation."""
    return re.findall(r"[A-Za-zÀ-ÿ']+", sentence)

def extract_latin_word(sentence: str) -> str | None:
    """
    Find the Latin word in a user's question by identifying the token
    that isn't in the English vocabulary.
    Returns the Latin word, or None if extraction is ambiguous.
    """
    tokens = tokenize(sentence)
    
    # Find tokens not in English vocab (case-insensitive check)
    non_english = [t for t in tokens if t.lower() not in ENGLISH_VOCAB]
    
    if len(non_english) == 1:
        # found one non english word
        return non_english[0]
    elif len(non_english) == 0:
        # found no non english words
        return None  # No Latin word found
    else:
        # found multiple non english words
        return None


# --- Helper functions -------------------------------------------------------------------

def get_response(user_input):
    print(f"[LOG] User input: {user_input}")

    # step 1: intent classification
    result = intent_classifier.classify(user_input)
    intent = result["intent"]
    confidence = result["confidence"]
    print(f"[LOG] Intent: {intent}, Confidence: {confidence}")

    # step 2: extract latin word
    # TODO: implement a better method for this
    latin_word = extract_latin_word(user_input)
    print(f"[LOG] Extracted Latin word: {latin_word}")

    # step 3: morphological analysis
    morphology = morphological_analyser.analyse(latin_word) if latin_word else None
    print(f"[LOG] Morphological analysis: {morphology}")

    # does identified pos match expected pos for identified intent? 
    # if not, fallback to an alternative response

    # step 3.5: checks before template filling

    # fallback: intent came as out of scope
    if intent == "oos":
        return RESPONSE_TEMPLATES["intents"][intent]["templates"][0]["text"]
        
    # fallback: no latin word found
    if not morphology:
        return f"I couldn't find a Latin word in your question. Could you rephrase?"

    analysis = morphology[0]  # single-word queries for now

    # fallback: unsupported intent (morphological analyser doesnt cover this feature)
    feature_key = INTENT_TO_FEATURE.get(intent)
    if feature_key is None:
        pretty = intent.replace("_", " ")
        return f"Sorry, I don't yet support questions about {pretty}."

    feature_data = analysis[feature_key]

    # fallback: the asked-about feature doesn't apply to this word's POS
    # (e.g. "what tense is puella" -> puella is a noun, so no tense)
    if feature_key != "pos" and not feature_data.get("applicable", True):
        pos_label = analysis["pos"]["label"]
        pretty = intent.replace("_", " ")
        return (f"The word '{latin_word}' is a {pos_label}, so it doesn't have a {pretty}.")

    # fallback: model isn't confident enough
    # (here is where i would fall back to the database)
    if feature_data.get("needs_fallback"):
        pretty = intent.replace("_", " ")
        return (f"I'm not confident about the {pretty} of '{latin_word}'. It might be a {feature_data['label']}, but I'm not sure.")

    # step 4: get response template for this intent
    template = RESPONSE_TEMPLATES["intents"][intent]["templates"][0]

    # step 5: fill in template with word + required morphological feature
    slot_values = {
        "WORD":           latin_word,
        "PART_OF_SPEECH": analysis["pos"]["label"],
        "PERSON":         analysis["person"]["label"],
        "MOOD":           analysis["mood"]["label"],
        "TENSE":          analysis["tense"]["label"],
        "VOICE":          analysis["voice"]["label"],
        "NUMBER":         analysis["number"]["label"],
        "CASE":           analysis["case"]["label"],
        "GENDER":         analysis["gender"]["label"],
    }

    response = template["text"]
    for slot in template["slots"]:
        response = response.replace("{" + slot + "}", str(slot_values[slot]))

    # step 6: return response
    print(f"[LOG] Response: {response}")
    return response

def log_message(session_id, chat_id, role, content):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO messages (session_id, chat_id, timestamp, role, content) VALUES (?, ?, ?, ?, ?)",
            (session_id, chat_id, datetime.utcnow().isoformat(), role, content)
        )

# --- Flask routes -----------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("landing.html")

@app.route("/chatbot")
def chatbot():
    return render_template("index_survey.html")

@app.route("/survey")
def survey():
    return render_template("survey.html")
    
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()
    session_id   = data.get("session_id", "").strip()
    chat_id      = data.get("chat_id", "").strip()

    if not user_message:
        return jsonify({"error": "Empty message"}), 400
    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400
    if not chat_id:
        return jsonify({"error": "Missing chat_id"}), 400

    log_message(session_id, chat_id, "user", user_message)

    bot_reply = get_response(user_message)
    log_message(session_id, chat_id, "bot", bot_reply)
    return jsonify({"response": bot_reply})

@app.route("/chatbot_with_survey/submit", methods=["POST"])
def submit_survey():
    data = request.get_json(silent=True) or {}

    # Coerce Likert fields to int (they arrive as strings from the form)
    likert_fields = ["easy_to_use", "understood_questions", "answers_accurate",
                     "answers_helpful", "enjoyed_using", "increased_interest", "would_recommend"]
    for f in likert_fields:
        try:
            data[f] = int(data[f]) if data.get(f) else None
        except (ValueError, TypeError):
            data[f] = None

    row = {
        "session_id":           data.get("session_id", ""),
        "timestamp":            datetime.utcnow().isoformat(),
        "latin_level":          data.get("latin_level", ""),
        "ai_familiarity":       data.get("ai_familiarity", ""),
        "easy_to_use":          data.get("easy_to_use"),
        "understood_questions": data.get("understood_questions"),
        "answers_accurate":     data.get("answers_accurate"),
        "answers_helpful":      data.get("answers_helpful"),
        "enjoyed_using":        data.get("enjoyed_using"),
        "increased_interest":   data.get("increased_interest"),
        "would_recommend":      data.get("would_recommend"),
        "liked_most":           data.get("liked_most", ""),
        "improvements":         data.get("improvements", ""),
        "other":                data.get("other", ""),
    }

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO responses (
                    session_id, timestamp, latin_level, ai_familiarity,
                    easy_to_use, understood_questions, answers_accurate,
                    answers_helpful, enjoyed_using, increased_interest, would_recommend,
                    liked_most, improvements, other
                ) VALUES (
                    :session_id, :timestamp, :latin_level, :ai_familiarity,
                    :easy_to_use, :understood_questions, :answers_accurate,
                    :answers_helpful, :enjoyed_using, :increased_interest, :would_recommend,
                    :liked_most, :improvements, :other
                )
            """, row)
        return jsonify({"status": "ok"})
    except sqlite3.Error as e:
        app.logger.exception("Failed to save survey response")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Main --------------------------------------------------------------------------------

if __name__ == "__main__":
    # app.run(debug=True)
    app.run(host='0.0.0.0', port=5000)

