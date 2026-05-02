from dataclasses import dataclass
from typing import Dict, Optional, Union

import torch
import torch.nn as nn
from transformers import PreTrainedConfig, PreTrainedModel, AutoModel, PreTrainedTokenizerBase
from transformers.modeling_outputs import ModelOutput

from morph_constants import FEATURE_ORDER, IGNORE_INDEX


# Multi-head model definition:


# create the custom configuration class
# inherits from pretrainedconfig class
# 4 additional member variables

class LatinMorphologicalAnalyserConfig(PreTrainedConfig):
  '''
  '''
  model_type = "latin_morphological_analyser"

  def __init__(self, bert_model_path="", num_labels_per_feat=None, pos_embed_dim=64, dropout=0.1, label2id_all=None, id2label_all=None, pos_feature_mask=None, initializer_range=0.02, **kwargs):
    super().__init__(**kwargs)
    self.bert_model_path = bert_model_path                # path to the pretrained latin bert model
    self.num_labels_per_feat = num_labels_per_feat or {}
    self.pos_embed_dim = pos_embed_dim
    self.dropout = dropout                                # dropout rate
    self.label2id_all = label2id_all or {}
    self.id2label_all = id2label_all or {}
    self.pos_feature_mask = pos_feature_mask or {}
    self.initializer_range = initializer_range



# A small two-layer MLP for classifying a single morphological feature.
# It receives both the raw BERT hidden state and a pos_context vector
# representing which POS the model currently thinks this token is.
# The concatenation [bert_repr, pos_context] lets the feature head condition its prediction on the POS
# — e.g. the tense head can look at POS confidence to know whether it should be predicting tense at all.

# a morphological feature head

class POSConditionedHead(nn.Module):
    """
    A 2-layer classification head that concatenates the BERT token
    embedding with a soft POS context vector before classifying.
    """
    def __init__(self, bert_hidden, pos_embed_dim, num_labels, dropout=0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(bert_hidden + pos_embed_dim, 256),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(256, num_labels),
        )

    def forward(self, bert_repr, pos_context):
        # bert_repr  : (..., bert_hidden)
        # pos_context: (..., pos_embed_dim)
        return self.net(torch.cat([bert_repr, pos_context], dim=-1))



# define a custom model output dataclass
# subclass of ModelOutput
# the data structure containing all the information returned by the model

@dataclass
class MorphologicalAnalyserOutput(ModelOutput):
  """
  Outputs of the morphological analyser model.
  """
  loss: torch.FloatTensor | None = None
  logits: torch.FloatTensor | None = None # POS logits
  feature_logits: Dict[str, torch.FloatTensor] | None = None
  hidden_states: tuple[torch.FloatTensor, ...] | None = None # proper BERT hidden states
  attentions: tuple[torch.FloatTensor, ...] | None = None



# create the top level model

class LatinMorphologicalAnalyser(PreTrainedModel):
  '''
  '''
  config_class = LatinMorphologicalAnalyserConfig
  base_model_prefix = "bert"##

  def __init__(self, config):
    super().__init__(config)

    self.bert = AutoModel.from_pretrained(config.bert_model_path) # load the pretrained latin bert weihhts

    hidden = self.bert.config.hidden_size # hidden layer number of input neruons

    # Reconstruct these from config instead of accepting as arguments
    self.label2id_all  = config.label2id_all
    self.id2label_all  = {feat: {int(k): v for k, v in d.items()} for feat, d in config.id2label_all.items()} # convert keys to int
    self.feature_order = FEATURE_ORDER

    # Rebuild the pos_mask tensor from config and register it as a buffer
    pos_mask = self._build_pos_mask(config)         # shape -> (num_pos, num_feats)
    self.register_buffer("pos_mask", pos_mask)

    num_pos = config.num_labels_per_feat["pos"]
    pos_embed_dim = config.pos_embed_dim
    dropout = config.dropout

    # creating the new layers:

    # POS head (no POS conditioning - feeds raw BERT repr)
    self.pos_dropout = nn.Dropout(dropout)     # dropiut layer
    self.pos_head = nn.Linear(hidden, num_pos) # a single linear layer mapping BERT's hidden states to POS logits

    # Soft POS conditioning embedding
    # pos_probs (batch, seq, num_pos) @ pos_embedding.weight (num_pos, dim)
    # → pos_context (batch, seq, dim)   [fully differentiable]
    self.pos_embedding = nn.Embedding(num_pos, pos_embed_dim)

    # One conditioned head per morphological feature
    self.feature_heads = nn.ModuleDict({
        feat: POSConditionedHead(
            bert_hidden   = hidden,
            pos_embed_dim = pos_embed_dim,
            num_labels    = config.num_labels_per_feat[feat],
            dropout       = dropout,
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
    # initialise the weights and biases for new layers added
    if isinstance(module, nn.Linear):
      module.weight.data.normal_(mean=0.0, std=self.config.initializer_range)
      if module.bias is not None:
        module.bias.data.zero_()
    elif isinstance(module, nn.Embedding):
      module.weight.data.normal_(mean=0.0, std=self.config.initializer_range)


  def forward(self, input_ids=None, attention_mask=None, labels_pos=None, labels_person=None, labels_number=None, labels_tense=None, labels_mood=None, labels_voice=None, labels_gender=None, labels_case=None, labels_degree=None, **kwargs):
    # forward pass thru the model

    # ── 1. BERT ────────────────────────────────────────────────────
    # pass inputs through the pretrained latin bert
    bert_out = self.bert(input_ids=input_ids, attention_mask=attention_mask)
    x = self.pos_dropout(bert_out.last_hidden_state)  # (B, T, H)

    # ── 2. POS classification ──────────────────────────────────────
    pos_logits = self.pos_head(x)                      # (B, T, num_pos)
    pos_probs  = torch.softmax(pos_logits, dim=-1)     # (B, T, num_pos)

    # ── 3. Soft POS context (differentiable weighted sum) ──────────
    pos_context = pos_probs @ self.pos_embedding.weight  # (B, T, pos_dim)

    # ── 4. Feature heads ───────────────────────────────────────────
    label_tensors = {
        "person": labels_person, "number": labels_number,
        "tense":  labels_tense,  "mood":   labels_mood,
        "voice":  labels_voice,  "gender": labels_gender,
        "case":   labels_case,   "degree": labels_degree,
    }
    feature_logits = {
        feat: head(x, pos_context)
        for feat, head in self.feature_heads.items()
    }   # each: (B, T, num_labels_for_feat)

    # ── 5. Loss ────────────────────────────────────────────────────
    loss = None
    if labels_pos is not None:
      import torch.nn.functional as F

      # POS loss — always computed for all valid tokens
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

        # Build a boolean mask: which tokens have this feature applicable?
        #   - token must not be padding (labels_pos != IGNORE_INDEX)
        #   - token's TRUE POS must have this feature active
        valid      = labels_pos != IGNORE_INDEX          # (B, T)
        pos_clamp  = labels_pos.clone()
        pos_clamp[~valid] = 0                            # safe index
        applicable = self.pos_mask[pos_clamp, feat_idx]  # (B, T) bool
        applicable = applicable & valid

        if applicable.any():
          feat_loss = F.cross_entropy(
              feature_logits[feat][applicable],   # (N, num_labels)
              feat_labels[applicable],            # (N,)
              ignore_index=IGNORE_INDEX,
          )
          loss = loss + feat_loss

    return MorphologicalAnalyserOutput(
        loss=loss,
        logits=pos_logits,
        feature_logits=feature_logits,
    )




# Define Custom Data Collator:

@dataclass
class MultiLabelDataCollator:
    tokenizer:           PreTrainedTokenizerBase
    padding:             Union[bool, str] = True
    max_length:          Optional[int]   = None
    label_pad_token_id:  int             = IGNORE_INDEX
    feat_names:          list            = None

    def __call__(self, features):
        label_keys = [f"labels_{f}" for f in self.feat_names]

        labels_dict = {k: [f[k] for f in features] for k in label_keys}
        stripped    = [{k: v for k, v in f.items()
                        if k not in label_keys} for f in features]

        batch   = self.tokenizer.pad(
            stripped, padding=self.padding,
            max_length=self.max_length, return_tensors="pt",
        )
        seq_len = batch["input_ids"].shape[1]

        for key, seqs in labels_dict.items():
            padded = [
                # Convert to list first — seq may be a tensor when
                # the dataset is in torch format (e.g. inside a DataLoader)
                list(seq) + [self.label_pad_token_id] * (seq_len - len(seq))
                for seq in seqs
            ]
            batch[key] = torch.tensor(padded, dtype=torch.long)

        return batch


