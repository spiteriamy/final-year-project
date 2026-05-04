'''
Defines service classes for the Morphological Analyser and Intent Classifier models.
Provides a clean interface for the Flask app.
Handles loading models from disk, preprocessing input text, and postprocessing output results.
'''

import os
import json

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from safetensors.torch import load_file
from .morphological_analyser import LatinMorphologicalAnalyser, LatinMorphologicalAnalyserConfig, predict_with_confidence

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

class MorphologicalAnalyserService:
    def __init__(self, model_path, bert_path, thresholds):
        # all the config loading, state_dict loading, etc.

        # Build fresh model from config

        self.thresholds = thresholds

        with open(os.path.join(model_path, "config.json")) as f:
            config = json.load(f)

        label2id_all = config["label2id_all"]
        self.id2label_all = {
            feat: {int(k): v for k, v in d.items()}
            for feat, d in config["id2label_all"].items()
        }
        self.pos_feature_mask = config["pos_feature_mask"]
        num_labels_per_feat = config["num_labels_per_feat"]
        
        morph_config = LatinMorphologicalAnalyserConfig(
            bert_model_path    = bert_path,
            num_labels_per_feat = num_labels_per_feat,
            label2id_all        = label2id_all,
            id2label_all = {feat: {str(k): v for k, v in d.items()} for feat, d in self.id2label_all.items()}, # convert int keys to str for JSON
            pos_feature_mask    = self.pos_feature_mask,
            pos_embed_dim      = 64,
            dropout            = 0.1,
        )

        model_loaded = LatinMorphologicalAnalyser(morph_config).to(DEVICE)

        # Load manually — bypasses from_pretrained's broken key remapping
        state_dict = load_file(
            os.path.join(model_path, "model.safetensors"),
            device=DEVICE
        )

        missing, unexpected = model_loaded.load_state_dict(state_dict, strict=False)

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = model_loaded.eval()  # set to inference mode

        self.FEATURE_ORDER = ["person", "number", "tense", "mood", "voice",  "gender", "case",  "degree"]

        self.pos_mask_tensor = self.build_pos_mask_tensor(label2id_all["pos"], DEVICE)
    

    def build_pos_mask_tensor(self, label2id_pos, device):
        """
        Build a (num_pos, num_features) bool tensor directly from POS_FEATURE_MASK.
        Any POS code not listed in POS_FEATURE_MASK gets all-False (no features).
        Unknown codes are reported so you can add them explicitly.
        """
        num_pos   = len(label2id_pos)
        num_feats = len(self.FEATURE_ORDER)
        mask      = torch.zeros(num_pos, num_feats, dtype=torch.bool)

        for pos_code, pos_idx in label2id_pos.items():
            if pos_code in self.pos_feature_mask:
                for fi, applicable in enumerate(self.pos_feature_mask[pos_code]):
                    mask[pos_idx, fi] = applicable
            else:
                # Surface any unmapped codes immediately rather than silently
                # treating them as all-False
                print(f"WARNING: POS code '{pos_code}' not in POS_FEATURE_MASK "
                      f"— all features will be masked off for this tag. "
                      f"Add it explicitly.")

        return mask.to(device)

    def analyse(self, text: str) -> list[dict]:
        # calls predict_with_confidence, returns clean results

        results = predict_with_confidence(
            text.split(), self.model, self.tokenizer, DEVICE,
            self.id2label_all, self.pos_mask_tensor, thresholds=self.thresholds,
        )

        return results


class IntentClassifierService:
    def __init__(self, model_path):
        '''
        Loads the intent classification model and tokenizer from disk.
        '''
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path).to(DEVICE)
        self.model.eval()  # set to inference mode

    def classify(self, text: str) -> dict:
        '''
        Classifies the intent of the input text.
        Returns intent label and confidence score.
        '''
        inputs = self.tokenizer(
            text, 
            return_tensors="pt", 
            truncation=True, 
            padding="max_length", 
            max_length=50
        ).to(DEVICE)

        with torch.no_grad():
            outputs = self.model(**inputs)

        probs = torch.softmax(outputs.logits, dim=1)
        prediction = probs.argmax(dim=1).item()
        confidence = probs.max().item()
        label_name = self.model.config.id2label[prediction]

        return {
            "intent": label_name,
            "confidence": confidence
        }

