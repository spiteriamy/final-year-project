'''Create a dataset of questions for intent classification task.'''

import pandas as pd
import json
import random
import re

# set to False to disable debug prints and use larger sample size
debug = False


def filter_by_labels(df: pd.DataFrame, labels: list) -> pd.DataFrame:
    '''
    Filter the dataframe to only rows that have all the specified labels filled in (not NaN).

    Filters the dataframe to the subset that contains only words
    that are valid for the target labels of the intent being asked about.
    '''
    mask = df[labels].notna().all(axis=1)
    return df[mask]


def sample_words(df: pd.DataFrame, n: int = 5000) -> pd.DataFrame:
    '''
    Sample n random rows from the dataframe. If the dataframe has fewer than n rows, return it as-is.
    '''
    if len(df) > n:
        return df.sample(n, random_state=42)
    return df


def fix_article(text: str) -> str:
    '''
    Fix "a"/"an" after template substitution.
    Replaces "a" with "an" and "A" with "An" when the following word starts with a vowel.
    '''
    text = re.sub(r'\ba ([aeiouAEIOU])', r'an \1', text)
    text = re.sub(r'\bA ([aeiouAEIOU])', r'An \1', text)
    return text


def fill_template(template_text: str, slots: list, word: str, placeholders: dict) -> tuple[str, dict]:
    '''
    Fill a question template string with actual values.

    For WORD slots: substitute the Latin word form directly.
    For other slots: pick a random value from placeholders[slot].

    Return:  
    text - the filled question string  
    filled_slots - dict of { slot_name: chosen_value } for every non-WORD slot that was substituted
    '''
    text = template_text
    filled_slots = {}

    # go through all slots that need to be filled in the template and substitute values
    for slot in slots:
        placeholder = f"{{{slot}}}"

        if slot == "WORD":
            # substitute with the latin word form
            text = text.replace(placeholder, word)
        else:
            # get all placeholder options for this slot
            options = [values for values in placeholders.get(slot, []) if values]
            if not options:
                # No valid options for this slot - leave placeholder as-is
                print(f"Warning: no valid options for slot '{slot}' - leaving placeholder as-is.")
                continue

            # choose a random option and substitute it in the text
            chosen = random.choice(options)
            text = text.replace(placeholder, chosen)
            filled_slots[slot] = chosen

    # fix article (a / an depending on next word) if needed after substitutions
    text = fix_article(text)

    return text, filled_slots
            


##

def build_answer_simple(target_labels: list, row: pd.Series) -> dict:
    '''
    Build the answer dict for a row.

    The answer is just the actual label value(s) from the dataframe row for the target labels.    
    '''
    answer = {label: row.get(label) for label in target_labels}
    return answer

# def build_answer(target_labels: list, row: pd.Series, filled_slots: dict) -> dict:
#     '''
#     Build the answer dict for a row.

#     For WORD-only templates (no filled_slots), the answer is just the
#     actual label value(s) from the dataframe row.

#     For multi-slot templates, also records what was asked and whether
#     it matches the actual value (yes/no questions):
#     '''
#     answer = {label: row.get(label) for label in target_labels}

#     return answer

# def build_answer(target_labels: list, row: pd.Series, filled_slots: dict) -> dict:
#     '''

#     For multi-slot templates, also records what was asked and whether
#     it matches the actual value (yes/no question semantics):
#         <label>_asked   - the data-format value implied by the question
#         <label>_correct - True/False whether the question's implied value
#                           matches the actual value
#     '''
    

#     for slot, chosen_text in filled_slots.items():
#         mapping = PLACEHOLDER_TO_DATA.get(slot, {})
#         chosen_data_value = mapping.get(chosen_text)

#         # Slot name -> label name: PART_OF_SPEECH -> part_of_speech
#         label_key = slot.lower()
#         actual_value = row.get(label_key)

#         answer[f"{label_key}_asked"] = chosen_data_value
#         answer[f"{label_key}_correct"] = (chosen_data_value == actual_value)

#     return answer



##


def build_dataset(templates_path: str, data_path: str, n: int = 1000) -> pd.DataFrame:
    '''
    Main dataset builder.
    This produces a balanced dataset with n examples per intent.

    templates_path - path to question_templates.json  
    data_path      - path to the words CSV (Latin words dataset)  
    n              - number of examples to sample per intent

    Return a DataFrame with columns: intent, question, word, answers, features
    '''
    # load question templates
    with open(templates_path, "r") as f:
        template_data = json.load(f)
    
    placeholders = template_data["placeholders"]
    intents = template_data["intents"]

    # load latin words dataset
    df = pd.read_csv(data_path, dtype=str)

    # generate dataset:

    examples = [] # list of DataFrames, one per intent, to concatenate at the end into the full dataset

    # iterate over all intents and generate questions/answers for each
    for intent_name, intent_data in intents.items():
        target_labels = intent_data["target_labels"]

        # filter out templates with empty text
        intent_templates = [t for t in intent_data["templates"] if t["text"]]
        if not intent_templates:
            print(f"Warning: intent '{intent_name}' has no templates - skipping.")
            continue

        # Filter and sample the dataframe for this intent's target labels
        # filter rows to only those that have all the required labels filled in
        # and check that the required columns exist first

        missing_cols = [l for l in target_labels if l not in df.columns]
        if missing_cols:
            print(f"Warning: intent '{intent_name}' requires columns {missing_cols} which are not in the dataframe - skipping.")
            continue

        # gets subset of dataframe that contains only
        # words that correspond to / are valid for the intent being asked about
        # eg if the intent is pos - any word is valid, if intent is person - only verbs, etc
        sub = filter_by_labels(df, target_labels)
        if sub.empty:
            print(f"Warning: intent '{intent_name}' has no rows with all labels populated - skipping.")
            continue

        # sample n random words from the dataset that work for this intent to be used with the templates
        # the words that will be used to fill the {WORD} slot in the templates
        sub = sample_words(sub, n=n)
        sub = sub.reset_index(drop=True)

        print(intent_name) if debug else None
        print(sub) if debug else None

        questions = []
        answers = []

        for i, row in sub.iterrows():
            # choose a random template
            template = random.choice(intent_templates)
            print("\ntemplate:", template) if debug else None

            # fill in the question template
            question, filled_slots = fill_template(
                template_text=template["text"],
                slots=template["slots"],
                word=row["form"],
                placeholders=placeholders
            )
            questions.append(question)

            print("generated question: ", question) if debug else None
            print("filled slots: ", filled_slots) if debug else None

            # build answers
            # answer = build_answer(target_labels, row, filled_slots)
            answer = build_answer_simple(target_labels, row)
            answers.append(answer)

            print("answer: ", answer) if debug else None

        # build the dataframe for this intent in bulk
        temp_df = pd.DataFrame({
            "intent": intent_name,
            "question": questions,
            "word": sub["form"].values,
            "answers": answers,
            "features": sub["features"].values,
        })

        examples.append(temp_df)

    if not examples:
        raise ValueError("No examples were generated. Check templates and data.")
    
    dataset = pd.concat(examples, ignore_index=True)
    return dataset



if __name__ == "__main__":
    dataset = build_dataset(
        templates_path="question_templates.json",
        data_path="words_data.csv",
        # n=1000
        n=5 if debug else 5000
    )

    # dataset summary
    print(f"\nDataset size: {len(dataset)} rows")
    print(f"Intents: {dataset['intent'].value_counts().to_dict()}")

    # save to file
    dataset.to_csv("data_test.csv", index=False)
    print("Saved to data_test.csv")





###### 




# ---------------------------------------------------------------------------
# Maps human-readable placeholder values (from JSON) to the data values
# used in the CSV (UniMorph/Whitaker format).
# Slot name (e.g. PART_OF_SPEECH) -> { human value -> data value }
# ---------------------------------------------------------------------------
# PLACEHOLDER_TO_DATA = {
#     "PART_OF_SPEECH": {
#         "noun":         "N",
#         "verb":         "V",
#         "adjective":    "ADJ",
#         "participle":   "V.PTCP",
#         "proper name":  "PROPN",
#         "adverb":       "ADV",
#     },
#     "MOOD": {
#         "indicative":   "IND",
#         "subjunctive":  "SBJV",
#         "imperative":   "IMP",
#     },
#     "TENSE": {
#         "present":  "PRS",
#         "past":     "PST",
#         "future":   "FUT",
#     },
#     "VOICE": {
#         "active":   "ACT",
#         "passive":  "PASS",
#     },
#     "ASPECT": {
#         "imperfective": "IPFV",
#         "perfective":   "PFV",
#         "perfect":      "PRF",
#     },
#     "NUMBER": {
#         "singular": "SG",
#         "plural":   "PL",
#     },
#     "CASE": {
#         "nominative":   "NOM",
#         "accusative":   "ACC",
#         "genitive":     "GEN",
#         "dative":       "DAT",
#         "ablative":     "ABL",
#         "vocative":     "VOC",
#     },
#     "GENDER": {
#         "masculine":    "MASC",
#         "feminine":     "FEM",
#         "neuter":       "NEUT",
#     },
#     "DECLENSION": {
#         "1st declension": "1",
#         "2nd declension": "2",
#         "3rd declension": "3",
#         "4th declension": "4",
#         "5th declension": "5",
#     },
#     "CONJUGATION": {
#         "1st conjugation": "1",
#         "2nd conjugation": "2",
#         "3rd conjugation": "3",
#         "4th conjugation": "4",
#     },
#     # PERSON and WORD are handled separately and don't need entries here.
# }



