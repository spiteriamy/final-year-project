'''Create a dataset of questions for intent classification task.'''

import os
import pandas as pd
import json
import random


def filter_by_labels(df, labels):
    mask = df[labels].notna().all(axis=1)
    return df[mask]


def sample_words(df, n=5000):
    if len(df) > n:
        return df.sample(n, random_state=42)
    return df


# Load question templates
with open("question_templates.json", "r") as file:
    templates = json.load(file)['intents']



# Load latin words dataset
# TEST DATASET FOR NOW
df = pd.read_csv("words_data_test_2.csv")


# Generate dataset

# number of questions per intent in dataset
n = 100

examples = []

for intent_name, intent_data in templates.items():
    target_labels = intent_data["target_labels"]

    templates = [t["text"] for t in intent_data["templates"] if t["text"]]
    if not templates:
        continue

    # Filter and sample
    sub = filter_by_labels(df, target_labels)
    sub = sample_words(sub, n=n) 

    # choose random templates for each row
    template_choices = random.choices(templates, k=len(sub))
    questions = [template.replace("{WORD}", word) for template, word in zip(template_choices, sub["form"])]

    # build answers as a list of dicts
    # this part not working for participle
    # taking V.PTCP as V
    # part_of_speech,Is adprobātūrum an adjective?,adprobātūrum,{'part_of_speech': 'V'},V.PTCP;ACC;MASC;SG
    answers = [
        {label: sub[label].iloc[i] for label in target_labels}
        for i in range(len(sub))
    ]

    # build the dataframe in bulk
    temp_df = pd.DataFrame({
        "intent": intent_name,
        "question": questions,
        "word": sub["form"].values,
        "answers": answers,
        "features": sub["features"].values,
    })

    examples.append(temp_df)

dataset = pd.concat(examples, ignore_index=True)



# save to file
dataset.to_csv("data.csv", index=False)


