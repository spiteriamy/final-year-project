'''
Morphological Analyser constant definitions
reused across the data preparation, training,
evaluation, and confidence-threshold notebooks.
'''


IGNORE_INDEX = -100



# **PROIEL morphology string decoder**  

# The PROIEL `morphology` field is a 10-char positional string.  
# Each character encodes one feature. Unused positions are "-".  
# Reference: https://dev.syntacticus.org/development-guide/#lemma-part-of-speech-and-morphology

# The final 2 characters ("strength" and "inflection") will be ignored.
# *   no records contain "strength" info
# *   "non-inflecting" tokens contain no other morphological information

# mapping of the meaning of each char in the morphology string
MORPH_POSITIONS = {
    0: ("person", {"1": "1", "2": "2", "3": "3", "x": "Unc", "-": "None"}),
    1: ("number", {"s": "Sing", "p": "Plur", "d": "Dual", "x": "Unc", "-": "None"}),
    2: ("tense", {"p": "Pres", "i": "Imp", "r": "Perf", "l": "Plup", "f": "Fut",
                  "t": "FutPerf", "u": "Past", "s": "Res", "a": "Aorist", "x": "Unc", "-": "None"}), # "s" = "resultative"
    3: ("mood", {"i": "Ind", "s": "Sub", "m": "Imp", "o": "Opt", "n": "Inf", "p": "Part",
                 "d": "Ger", "g": "Gdv", "u": "Sup", "x": "Unc", "y": "FinUnsp", "e": "IndOrSub",
                 "f": "IndOrImp", "h": "SubOrImp", "t": "Fin", "-":"None"}),
    4: ("voice", {"a": "Act", "p": "Pass", "m": "Mid", "e": "MidOrPass", "x": "Unsp", "-": "None"}),
    5: ("gender", {"m": "Masc", "f": "Fem", "n": "Neut",
                   "p": "MascFem", "o": "MascNeut", "r": "FemNeut",
                   "q": "MascFemNeut", "x": "Unc", "-": "None"}),
    6: ("case", {"n": "Nom", "g": "Gen", "d": "Dat", "a": "Acc",
                 "b": "Abl", "v": "Voc", "l": "Loc", "o": "Obl",
                 "c": "GenDat", "e": "AccDat", "i": "Instr", "x": "Unc",
                 "z": "No", "-": "None"}),
    7: ("degree", {"p": "Pos", "c": "Comp", "s": "Sup", "x": "Unc", "z": "No", "-": "None"}),
    # 8: ("strength", {"w": "Weak", "s": "Strong", "t": "WkOrSt"}), # "t": "weak or strong"
    # 9: ("inflection", {"n": "NonInf", "i": "Inf"})                # non-inflecting, inflecting
}

# the order in which each feature appears in the morphology string
FEATURE_ORDER = ["person", "number", "tense", "mood", "voice",  "gender", "case",  "degree"]

ALL_FEATS = ["pos"] + FEATURE_ORDER




# **POS -> feature compatibility matrix**
# Maps each specific PROIEL POS code to its applicable features, 
# defines which of the morphological features are applicable per POS.
# Order matches `FEATURE_ORDER`: person, number, tense, mood, voice, gender, case, degree

#          per    num    tense  mood   voice  gender case   degree
POS_FEATURE_MASK = {
    "A-": [False, True,  False, False, False, True,  True,  True  ],  # adjective
    "C-": [False, False, False, False, False, False, False, False ],  # conjunction
    "Df": [False, False, False, False, False, False, False, True  ],  # adverb
    "Dq": [False, False, False, False, False, False, False, False ],  # relative adverb
    "Du": [False, False, False, False, False, False, False, False ],  # interrogative adverb
    "F-": [False, False, False, False, False, False, False, False ],  # foreign word
    "G-": [False, False, False, False, False, False, False, False ],  # subjunction
    "I-": [False, False, False, False, False, False, False, False ],  # interjection
    "Ma": [False, True,  False, False, False, True,  True,  False ],  # cardinal numeral
    "Mo": [False, True,  False, False, False, True,  True,  False ],  # ordinal numeral
    "N-": [False, False, False, False, False, False, False, False ],  # infinitive marker (not found in corpus)
    "Nb": [False, True,  False, False, False, True,  True,  False ],  # common noun
    "Ne": [False, True,  False, False, False, True,  True,  False ],  # proper noun
    "Pc": [False, True,  False, False, False, True,  True,  False ],  # reciprocal pronoun
    "Pd": [False, True,  False, False, False, True,  True,  False ],  # demonstrative pronoun
    "Pi": [False, True,  False, False, False, True,  True,  False ],  # interrogative pronoun
    "Pk": [True,  True,  False, False, False, True,  True,  False ],  # personal reflexive pronoun
    "Pp": [True,  True,  False, False, False, True,  True,  False ],  # personal pronoun
    "Pr": [False, True,  False, False, False, True,  True,  False ],  # relative pronoun
    "Ps": [True,  True,  False, False, False, True,  True,  False ],  # possessive pronoun
    "Pt": [True,  True,  False, False, False, True,  True,  False ],  # possessive reflexive pronoun
    "Px": [False, True,  False, False, False, True,  True,  False ],  # indefinite pronoun
    "Py": [False, False, False, False, False, False, False, False ],  # quantifier (not found in corpus)
    "R-": [False, False, False, False, False, False, False, False ],  # preposition
    "S-": [False, False, False, False, False, False, False, False ],  # article (not found in corpus)
    "V-": [True,  True,  True,  True,  True,  False, False, False ],  # verb
    "X-": [False, False, False, False, False, False, False, False ]   # unassigned
}

