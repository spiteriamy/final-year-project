'''
Create a smaller sample dataset containing a subset of the data, 
containing a few examples of each part of speech and morphological features.
For easier testing.
'''

import pandas as pd

# Load unimorph data
df = pd.read_csv("/home/amys/words/lat/lat", sep="\t", names=["lemma", "form", "features"])

# Extract features in unimorph data

df["part_of_speech"] = df["features"].str.findall(r'\b(V\.PTCP|V\.MSDR|ADJ|PROPN|N|V)\b').apply(lambda x: '+'.join(x)) # joins multiple pos tags into 1 combined tag with +
df["gender"] = df["features"].str.extract(r'\b(MASC\+FEM\+NEUT|MASC\+FEM|MASC\+NEUT|FEM\+NEUT|MASC|FEM|NEUT)\b')
df["case"] = df["features"].str.extract(r'\b(GEN\+DAT|NOM|ACC|GEN|DAT|ABL|VOC|LOC)\b')
df["number"] = df["features"].str.extract(r'\b(SG|PL)\b')
df["tense"] = df["features"].str.extract(r'\b(PRS|FUT|PST)\b')
df["voice"] = df["features"].str.extract(r'\b(ACT|PASS)\b')
df["mood"] = df["features"].str.extract(r'\b(IND|SBJV|IMP)\b')
df["person"] = df["features"].str.extract(r'\b(1|2|3)\b')
df["aspect"] = df["features"].str.extract(r'\b(IPFV|PFV|PRF)\b')
df["finiteness"] = df["features"].str.extract(r'\b(NFIN)\b')
df["lang_specific"] = df["features"].str.extract(r'\b(LGSPEC1)\b') # supine

# create a smaller sample dataset with a few examples of each part of speech
sample_df = pd.DataFrame()

for pos in ["ADJ", "V", "N", "PROPN", "V\.PTCP", "V\+V\.PTCP", "V\.MSDR", "V\+V\.MSDR"]:
    pos_df = df[df['part_of_speech'].str.fullmatch(pos)].head(15)  # take first 15 examples of each POS
    sample_df = pd.concat([sample_df, pos_df])


# save dataframe to file
sample_df.to_csv("/home/amys/words/sample_data.csv", index=False)
