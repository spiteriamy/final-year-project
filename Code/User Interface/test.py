import re
from nltk.corpus import words
# Run once: nltk.download('words')

ENGLISH_VOCAB = set(w.lower() for w in words.words())

# Add common chatbot/grammar terms that might not be in the corpus
# EXTRA_ENGLISH = {
#     "what's", "i'm", "don't", "doesn't", "isn't", "you", "your",
#     "tense", "mood", "voice", "case", "gender", "number", "person",
#     "conjugation", "declension", "parse", "analyze", "morphology",
#     "verb", "noun", "adjective", "adverb", "pronoun",
#     "ok", "okay", "hi", "hey", "please", "thanks",
# }
# ENGLISH_VOCAB.update(EXTRA_ENGLISH)

def tokenize(sentence: str) -> list[str]:
    """Split on whitespace and strip punctuation, preserving original casing for output."""
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
        return non_english[0]
    elif len(non_english) == 0:
        return None  # No Latin word found
    else:
        # Ambiguous — multiple unknown tokens
        # Heuristic: prefer the longest, or the last one (often the target)
        # return max(non_english, key=len)
        return None

# Examples
test_sentences = [
    "What is the tense of amavit?",
    "Can you parse currunt for me?",
    "What case is puellae in?",
    "Tell me about the word rosarum please",
    "What is the part of speech of ego?",
    "Are amavit and puellae adjective?"
]

for s in test_sentences:
    print(f"{s!r} -> {extract_latin_word(s)}")