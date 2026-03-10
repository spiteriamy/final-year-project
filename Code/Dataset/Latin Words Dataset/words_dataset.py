'''
Script to extract additional morphological information from Whitaker's Words program
to supplement missing information in the unimorph latin dataset.
'''

# TODO: combined tags handling

# combined gender tags:

# whitakers words:
# gender is common (C), that is, it may be masculine or feminine
# X,         --  all, none, or unknown
# C          --  Common (masculine and/or feminine)

# unimorph                = whitakers words

# FEM+FEM   -> FEM        = F

# MASC+FEM                = C, sometimes M and F

# FEM+MASC                = words returns records with both M and F, and sometimes even N and C

# FEM+NEUT                = words returns records both with N and F (25 total records)

# MASC+FEM+NEUT           = X

# MASC+NEUT               = words returns records both with N and M

# NEUT+MASC               = the 8 examples found in unimorph are listed as N in Words


# combined case tags:

# GEN+DAT                 = in words, separate records with GEN and DAT

import os
import pandas as pd
# from words import Words
from words_new import Words
from tqdm import tqdm


debug = True

tqdm.pandas()

def safe_analyze(word):
    """Wrapper to avoid crashes inside w.analyze()."""
    try:
        return w.analyze(word)
    except Exception as e:
        print(f"Error analyzing {word}: {e}")
        return []


def check(form_info: list[dict], df_row: pd.Series) -> dict:
    """
    Use the information in df_row to check if an entry 
    for a word form matches one of the word forms in form_info.
    Returns the matching word form's information.

    Finds which of the word forms returned by Words best matches
    the UniMorph row, by comparing POS and relevant features
    (e.g. case+number for nouns, tense+mood+voice+person+number for verbs)

    form_info: list of word forms along with their info (from whitakers words)

    df_row: the row in the df (from unimorph) where the word form is the same as the ones in form_info
    """

    # for each word form in form_info, start comparing the feature values
    # to the values in the unimorph row
    # the best matching one in form_info, will be selected as the match
    # to be used to fill in the missing info in unimorph from it

    # different checks for different parts of speech

    for entry in form_info:
        if entry.get('part_of_speech') == 'N':
            # check pos and skip if not noun
            uni_pos = df_row.get('part_of_speech')
            if uni_pos != 'N':
                continue

            # check if case and number match
            words_case = entry.get('case')
            uni_case = df_row.get('case')

            words_num = entry.get('number')
            uni_num = df_row.get('number')

            # TODO: handle combined case tags
            if (words_case != uni_case):
                continue # no match - skip to next entry

            if (uni_num == 'SG' and words_num != 'S') or (uni_num == 'PL' and words_num != 'P'):
                continue

            # found match so return it
            return entry

        elif entry.get('part_of_speech') == 'V':
            # check pos
            uni_pos = df_row.get('part_of_speech')
            if uni_pos != 'V':
                continue

            # mood, voice, tense, (optionally aspect), person, number
            words_mood = entry.get('mood')
            uni_mood = df_row.get('mood')

            words_voice = entry.get('voice')
            uni_voice = df_row.get('voice')

            words_tense = entry.get('tense')
            uni_tense = df_row.get('tense')
            uni_aspect = df_row.get('aspect')

            words_person = entry.get('person')
            uni_person = df_row.get('person')

            words_num = entry.get('number')
            uni_num = df_row.get('number')

            if (uni_mood == 'SBJV' and words_mood != 'SUB') or (uni_mood == 'IND' and words_mood != 'IND') or (uni_mood == 'IMP' and words_mood != 'IMP'):
                continue 

            # words voice may sometimes be missing
            if words_voice != None:
                if (uni_voice == 'ACT' and words_voice != 'ACTIVE') or (uni_voice == 'PASS' and words_voice != 'PASSIVE'):
                    continue 

            # tense needs to be combined with aspect
            # in unimorph - tense and aspect separate, in words both are just tense
            if uni_tense == 'PRS' and words_tense != 'PRES':
                continue
            elif uni_tense == 'FUT':
                if uni_aspect == None and words_tense != 'FUT':
                    continue
                if uni_aspect == 'PRF' and words_tense != 'FUTP': # FUTP (w) = FUT;PRF; (u)
                    continue
            elif uni_tense == 'PST':
                if uni_aspect == 'IPFV' and words_tense != 'IMPF': # IMPF (w) = PST;IPFV (u)
                    continue
                if uni_aspect == 'PFV' and words_tense != 'PERF': # PERF (w) = PST;PFV (u)
                    continue
                if uni_aspect == 'PRF' and words_tense != 'PLUP': # PLUP (w) = PST;PRF; (u)
                    continue

            if (words_person != uni_person):
                continue

            if (uni_num == 'SG' and words_num != 'S') or (uni_num == 'PL' and words_num != 'P'):
                continue

            return entry
        
        elif entry.get('part_of_speech') == 'ADJ':
            # check pos
            uni_pos = df_row.get('part_of_speech')
            if uni_pos != 'ADJ':
                continue

            # case, gender, number
            words_case = entry.get('case')
            uni_case = df_row.get('case')

            words_num = entry.get('number')
            uni_num = df_row.get('number')

            words_gender = entry.get('gender')
            uni_gender = df_row.get('gender')

            # TODO: revise combined case tag handling
            # for now, just check if the case in words matches either of the cases in the combined tag in unimorph

            # if it is not the combined tag, then the case in unimorph and words should match exactly
            if uni_case != 'GEN+DAT':
                if (words_case != uni_case):
                    continue

            # if it is the combined tag, then the case in words should be either GEN or DAT
            if uni_case == 'GEN+DAT':
                if (words_case != 'GEN' and words_case != 'DAT'):
                    continue

            if (uni_num == 'SG' and words_num != 'S') or (uni_num == 'PL' and words_num != 'P'):
                continue

            # TODO: handle combined gender tags
            # words has additional gender tags like C, X
            if (uni_gender == 'MASC' and words_gender != 'M') or (uni_gender == 'FEM' and words_gender != 'F') or (uni_gender == 'NEUT' and words_gender != 'N'):
                continue

            return entry

        elif entry.get('part_of_speech') == 'VPAR':
            # check pos
            uni_pos = df_row.get('part_of_speech')
            if uni_pos not in ('V.PTCP', 'V+V.PTCP', 'V.MSDR', 'V+V.MSDR'):
                continue

            # different checks for V.PTCP and V+V.PTCP
            if uni_pos == 'V.PTCP': 
                # compare case, gender, number
                words_case = entry.get('case')
                uni_case = df_row.get('case')

                words_num = entry.get('number')
                uni_num = df_row.get('number')

                words_gender = entry.get('gender')
                uni_gender = df_row.get('gender')

                # TODO: revise combined case tag handling

                # if it is not the combined tag, then the case in unimorph and words should match exactly
                if uni_case != 'GEN+DAT':
                    if (words_case != uni_case):
                        continue

                # if it is the combined tag, then the case in words should be either GEN or DAT
                if uni_case == 'GEN+DAT':
                    if (words_case != 'GEN' and words_case != 'DAT'):
                        continue

                if (uni_num == 'SG' and words_num != 'S') or (uni_num == 'PL' and words_num != 'P'):
                    continue

                # TODO: handle combined gender tags
                # words has additional gender tags like C, X
                if (uni_gender == 'MASC' and words_gender != 'M') or (uni_gender == 'FEM' and words_gender != 'F') or (uni_gender == 'NEUT' and words_gender != 'N'):
                    continue

            elif uni_pos == 'V+V.PTCP': 
                # compare voice, tense, aspect
                words_voice = entry.get('voice')
                uni_voice = df_row.get('voice')
                words_tense = entry.get('tense')
                uni_tense = df_row.get('tense')
                uni_aspect = df_row.get('aspect')

                if words_voice != None:
                    if (uni_voice == 'ACT' and words_voice != 'ACTIVE') or (uni_voice == 'PASS' and words_voice != 'PASSIVE'):
                        continue 

                if uni_tense == 'PRS' and words_tense != 'PRES':
                    continue
                elif uni_tense == 'FUT':
                    if uni_aspect == None and words_tense != 'FUT':
                        continue
                    if uni_aspect == 'PRF' and words_tense != 'FUTP': # FUTP (w) = FUT;PRF; (u)
                        continue
                elif uni_tense == 'PST':
                    if uni_aspect == 'IPFV' and words_tense != 'IMPF': # IMPF (w) = PST;IPFV (u)
                        continue
                    if uni_aspect == 'PFV' and words_tense != 'PERF': # PERF (w) = PST;PFV (u)
                        continue
                    if uni_aspect == 'PRF' and words_tense != 'PLUP': # PLUP (w) = PST;PRF; (u)
                        continue

            elif uni_pos in ('V.MSDR', 'V+V.MSDR'):
                # skip supines
                if df_row.get('lang_specific') == "LGSPEC1":
                    continue

                # compare case
                words_case = entry.get('case')
                uni_case = df_row.get('case')

                # TODO: handle combined case tags
                if (words_case != uni_case):
                    continue

            return entry

        elif entry.get('part_of_speech') == 'SUPINE':
            # for SUPINE, need to check if unimorph has LGSPEC1 tag
            if df_row.get('lang_specific') != "LGSPEC1":
                # if the word is not labeled as supine in unimorph, skip
                continue

            # compare case
            words_case = entry.get('case')
            uni_case = df_row.get('case')

            # TODO: revise combined case tag handling

            # if it is not the combined tag, then the case in unimorph and words should match exactly
            if uni_case != 'GEN+DAT':
                if (words_case != uni_case):
                    continue

            # if it is the combined tag, then the case in words should be either GEN or DAT
            if uni_case == 'GEN+DAT':
                if (words_case != 'GEN' and words_case != 'DAT'):
                    continue

            return entry
        
        else:
            # skip other parts of speech since unimorph does not contain
            continue
    

def get_tag_mapping(field: str) -> dict:
    """
    Return a mapping of the relevant tags for the given field (e.g. case, number, tense, etc.)
    between the tags used in Words and the tags used in unimorph.
    """
    if field == "number":
        return {
            "S": "SG",
            "P": "PL"
        }
    elif field == "gender": # TODO: handle combined gender tags
        return {
            "M": "MASC",
            "F": "FEM",
            "N": "NEUT"
        }
    elif field == "tense":
        return {
            "PRES": "PRS",
            "IMPF": "PST",
            "PERF": "PST",
            "PLUP": "PST",
            "FUT": "FUT",
            "FUTP": "FUT"
        }
    elif field == "aspect":
        return {
            "IMPF": "IPFV",
            "PERF": "PFV",
            "PLUP": "PRF",
            "FUTP": "PRF"
        }
    elif field == "mood":
        return {
            "IND": "IND",
            "SUB": "SBJV",
            "IMP": "IMP"
        }
    elif field == "voice":
        return {
            "ACTIVE": "ACT",
            "PASSIVE": "PASS"
        }
    elif field == "person":
        return {
            "1": "1", 
            "2": "2", 
            "3": "3"
        }
    elif field == "case": # TODO: handle combined case tags
        return {
            "NOM": "NOM", 
            "GEN": "GEN", 
            "DAT": "DAT", 
            "ACC": "ACC", 
            "ABL": "ABL", 
            "VOC": "VOC", 
            "LOC": "LOC"
        }


def extract_info(entries, row: pd.Series) -> dict:
    """
    Extract the new info from the Words.analyze() output (entries)
    to create 5 new fields for the dataframe
    and also fill in any gaps in existing fields in the row.

    entries = result of Words.analyze(word)  
    row = row in df from unimorph  
    Return a dict with fields to add to dataframe.
    """
    
    # initialize the new columns to be added to the df
    output = {
        "conjugation": None,
        "declension": None,
        "degree": None,
        "participle_type": None,
        "comment": None
    }

    if not entries: # Words.analyze() returned no output
        return output
    
    # Flatten all possible word forms across all lemma options
    # to create one long list of forms
    all_forms = []
    for entry in entries:
        for f in entry["forms"]:
            all_forms.append(f)

    # find which of the word forms in all_forms best matches the unimorph row
    # this would be the form that has the same POS and relevant features as the unimorph row
    # meaning it would be the same form of the same lemma as the one in the unimorph row
    # just with more info provided by Words
    matches = check(all_forms, row) or {}
    if matches == {}:
        return output

    # fill in the already existing columns that have missing values with the info from matches
    # For every UniMorph column that exists in matches,
    # fill in missing values but DO NOT overwrite existing ones.
    fillable_fields = [
        "case", "number", "gender", "person",
        "tense", "aspect", "voice", "mood"
    ]

    # for tense and aspect, need to split combined tense in Words
    # unimorph has separate columns for tense and aspect, 
    # but Words combines them into one tag (tense)

    # fill in missing values in the existing columns
    for field in fillable_fields:
        if field in row.index:
            # Check if UniMorph has missing value
            if pd.isna(row[field]) or row[field] in (None, ""):
                # convert Whitaker values to UniMorph style tags

                mapping = get_tag_mapping(field)

                if field == "aspect":
                    output[field] = mapping.get(matches.get("tense"), None)
                else:
                    output[field] = mapping.get(matches.get(field), None)


    # fill in the new columns
    output["conjugation"] = matches.get("conjugation")
    output["declension"] = matches.get("declension")
    output["degree"] = matches.get("degree")
    output["participle_type"] = matches.get("participle_type")
    output["comment"] = matches.get("comment")

    return output



if __name__ == "__main__":

    if debug:
        # load sample data for testing
        df = pd.read_csv("/home/amys/words/sample_data.csv", dtype=str)

    else:
        # Load unimorph data
        df = pd.read_csv("/home/amys/words/lat/lat", sep="\t", names=["lemma", "form", "features"])

        # Extract features in unimorph data
        # create new columns for each feature by extracting from the "features" column

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

    
    print(df.head())


    # make instance of words
    w = Words()

    # use words program to add conjugation and
    # declension info for each word in the dataset

    # new columns to be added:
    # conjugation, declension, degree, participle_type, comment

    # analyze dataset with Whitaker's Words
    # creates new column "analysis" with the full analysis result for each word
    # df["analysis"] = df["form"].apply(safe_analyze)
    df["analysis"] = df["form"].progress_apply(safe_analyze)

    # extract new columns info:

    # apply the extract_info function to each row in the df
    # which will return a dict of new fields to add to the dataframe
    # which will be added as new columns in the dataframe

    # extract_info will take the analysis result for the word in that row
    # and the existing data from the unimorph dataset row
    # to create new fields for the dataframe.

    # df_extract = df.apply(lambda row: extract_info(row["analysis"], row), axis=1)
    df_extract = df.progress_apply(lambda row: extract_info(row["analysis"], row), axis=1)
    df_extract = df_extract.apply(pd.Series)

    for col in df_extract.columns: # add new columns to df
        if col not in df.columns:
            df[col] = df_extract[col]

    df.update(df_extract, overwrite=False) # update existing columns in df with new info

    # drop analysis column
    df = df.drop('analysis', axis=1)


    # save dataframe to file
    df.to_csv("/home/amys/words/words_data.csv", index=False)


    # close words program
    w.close()

