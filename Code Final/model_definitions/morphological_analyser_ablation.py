'''
Ablation study variant of the morphological analyser.

Identical to LatinMorphologicalAnalyser EXCEPT:
  - Feature heads receive only the BERT representation
    (no concatenated pos_context vector).
  - No POS embedding layer.

Everything else (BERT backbone, POS head, pos_mask buffer, loss
masking based on TRUE labels_pos) is unchanged so the comparison
isolates the conditioning as the single variable.
'''

# from dataclasses import dataclass
# from typing import Dict, Optional, Union

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import PreTrainedConfig, PreTrainedModel, BertModel, PreTrainedTokenizerBase
from transformers.modeling_outputs import ModelOutput

from morph_constants import FEATURE_ORDER, IGNORE_INDEX
from morphological_analyser import MorphologicalAnalyserOutput



# A 2-layer MLP for classifying a single morphological feature.
# Receives ONLY the raw BERT hidden state — no POS context.
# Same hidden size (256) and dropout as POSConditionedHead so the
# only structural difference between the two models is the absence
# of pos_context in the input.

class POSUnconditionedHead(nn.Module):
    """
    A 2-layer classification head that receives only the BERT token
    embedding. No POS conditioning.
    """
    def __init__(self, bert_hidden, num_labels, dropout=0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(bert_hidden, 256),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(256, num_labels),
        )

    def forward(self, bert_repr):
        # bert_repr: (..., bert_hidden)
        return self.net(bert_repr)



# config for the no-POS-conditioning variant

class LatinMorphologicalAnalyserNoPOSCondConfig(PreTrainedConfig):
  '''
  '''
  model_type = "latin_morphological_analyser_no_pos_cond"

  def __init__(self, bert_model_path="", num_labels_per_feat=None, dropout=0.1, label2id_all=None, id2label_all=None, pos_feature_mask=None, initializer_range=0.02, **kwargs):
    super().__init__(**kwargs)
    self.bert_model_path = bert_model_path
    self.num_labels_per_feat = num_labels_per_feat or {}
    self.dropout = dropout
    self.label2id_all = label2id_all or {}
    self.id2label_all = id2label_all or {}
    self.pos_feature_mask = pos_feature_mask or {}
    self.initializer_range = initializer_range



# top-level no-POS-conditioning model

class LatinMorphologicalAnalyserNoPOSCond(PreTrainedModel):
  '''
  Ablation baseline: identical pipeline to LatinMorphologicalAnalyser but
  the feature heads receive only the BERT representation. Used to test
  whether the soft POS conditioning earns its complexity.
  '''
  config_class = LatinMorphologicalAnalyserNoPOSCondConfig

  def __init__(self, config):
    super().__init__(config)

    self.bert = BertModel.from_pretrained(config.bert_model_path)

    hidden = self.bert.config.hidden_size

    self.label2id_all  = config.label2id_all
    self.id2label_all  = {feat: {int(k): v for k, v in d.items()} for feat, d in config.id2label_all.items()}
    self.feature_order = FEATURE_ORDER

    pos_mask = self._build_pos_mask(config)
    self.register_buffer("pos_mask", pos_mask)

    num_pos = config.num_labels_per_feat["pos"]
    dropout = config.dropout

    # POS head — same as the conditioned model
    self.pos_dropout = nn.Dropout(dropout)
    self.pos_head    = nn.Linear(hidden, num_pos)

    # NOTE: no pos_embedding layer — that's the whole point of the ablation.

    # Unconditioned feature heads
    self.feature_heads = nn.ModuleDict({
        feat: POSUnconditionedHead(
            bert_hidden = hidden,
            num_labels  = config.num_labels_per_feat[feat],
            dropout     = dropout,
        )
        for feat in FEATURE_ORDER
    })

    self.post_init()


  def _build_pos_mask(self, config):
    label2id_pos = config.label2id_all["pos"]
    num_pos = len(label2id_pos)
    num_feats = len(FEATURE_ORDER)
    mask = torch.zeros(num_pos, num_feats, dtype=torch.bool)

    for pos_code, pos_idx in label2id_pos.items():
      if pos_code in config.pos_feature_mask:
        for fi, applicable in enumerate(config.pos_feature_mask[pos_code]):
          mask[pos_idx, fi] = applicable

    return mask


  def _init_weights(self, module):
    if isinstance(module, nn.Linear):
      module.weight.data.normal_(mean=0.0, std=self.config.initializer_range)
      if module.bias is not None:
        module.bias.data.zero_()
    elif isinstance(module, nn.Embedding):
      module.weight.data.normal_(mean=0.0, std=self.config.initializer_range)


  def forward(self, input_ids=None, attention_mask=None, labels_pos=None, labels_person=None, labels_number=None, labels_tense=None, labels_mood=None, labels_voice=None, labels_gender=None, labels_case=None, labels_degree=None, **kwargs):

    # ── 1. BERT ────────────────────────────────────────────────────
    bert_out = self.bert(input_ids=input_ids, attention_mask=attention_mask)
    x = self.pos_dropout(bert_out.last_hidden_state)  # (B, T, H)

    # ── 2. POS classification ──────────────────────────────────────
    pos_logits = self.pos_head(x)                     # (B, T, num_pos)

    # ── 3. Feature heads — no POS context, just BERT repr ──────────
    label_tensors = {
        "person": labels_person, "number": labels_number,
        "tense":  labels_tense,  "mood":   labels_mood,
        "voice":  labels_voice,  "gender": labels_gender,
        "case":   labels_case,   "degree": labels_degree,
    }
    feature_logits = {
        feat: head(x)
        for feat, head in self.feature_heads.items()
    }   # each: (B, T, num_labels_for_feat)

    # ── 4. Loss (same masking logic as the conditioned model) ──────
    loss = None
    if labels_pos is not None:
      pos_loss = F.cross_entropy(
          pos_logits.view(-1, pos_logits.size(-1)),
          labels_pos.view(-1),
          ignore_index=IGNORE_INDEX,
      )
      loss = pos_loss

      for feat_idx, feat in enumerate(FEATURE_ORDER):
        feat_labels = label_tensors[feat]
        if feat_labels is None:
            continue

        # Same mask construction as in the conditioned model:
        #   - token must not be padding (labels_pos != IGNORE_INDEX)
        #   - token's TRUE POS must have this feature active
        valid      = labels_pos != IGNORE_INDEX
        pos_clamp  = labels_pos.clone()
        pos_clamp[~valid] = 0
        applicable = self.pos_mask[pos_clamp, feat_idx]
        applicable = applicable & valid

        if applicable.any():
          feat_loss = F.cross_entropy(
              feature_logits[feat][applicable],
              feat_labels[applicable],
              ignore_index=IGNORE_INDEX,
          )
          loss = loss + feat_loss

    # Reuse the same output dataclass so downstream code (collators,
    # eval functions) doesn't need to special-case the ablation model.
    return MorphologicalAnalyserOutput(
        loss=loss,
        logits=pos_logits,
        feature_logits=feature_logits,
    )

