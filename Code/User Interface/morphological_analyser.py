from dataclasses import dataclass
from typing import Dict
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModel, PreTrainedModel, PreTrainedConfig, BertModel
from transformers.modeling_outputs import ModelOutput


IGNORE_INDEX = -100
FEATURE_ORDER = ["person", "number", "tense", "mood", "voice",  "gender", "case",  "degree"]


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



class LatinMorphologicalAnalyser(PreTrainedModel):
  '''
  '''
  config_class = LatinMorphologicalAnalyserConfig
  # base_model_prefix = "bert"##

  def __init__(self, config):
    super().__init__(config)

    # self.bert = AutoModel.from_pretrained(config.bert_model_path) # load the pretrained latin bert weihhts
    # self.bert = AutoModel.from_pretrained(config.bert_model_path, local_files_only=True) # treat it as a local path, never hit the Hub
    self.bert = BertModel.from_pretrained(config.bert_model_path)

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



def predict_with_confidence(
    sentence_words, model, tokenizer, device,
    id2label_all, pos_mask_tensor, thresholds=None,
):
    """
    Predict morphological features with confidence scores and fallback flags.

    Args:
        sentence_words: list of word strings
        model, tokenizer, device: as usual
        id2label_all: label vocabularies
        pos_mask_tensor: POS-feature compatibility mask
        feature_order: list of feature names
        thresholds: dict[feat] -> float threshold, or single float for all.
                    If None, no thresholding (all predictions accepted).

    Returns:
        list of dicts, one per word. Each dict contains:
          - "word": the input word
          - "pos": {"label": str, "confidence": float, "needs_fallback": bool}
          - "person": {"label": str, "confidence": float, "needs_fallback": bool}
          - ... (for each applicable feature)
          - features not applicable for the predicted POS get:
            {"label": "—", "confidence": None, "needs_fallback": False, "applicable": False}
    """
    model.eval()
    words_lower = [w.lower() for w in sentence_words]

    encoding = tokenizer(
        words_lower,
        is_split_into_words=True,
        return_tensors="pt",
        truncation=True,
        max_length=128,
    ).to(device)

    word_ids = encoding.word_ids(batch_index=0)

    with torch.no_grad():
        output = model(**encoding)

    pos_logits = output.logits[0]               # (seq_len, num_pos)
    feature_logits = output.feature_logits


    pos_probs = F.softmax(pos_logits, dim=-1)
    pos_conf, pos_pred = pos_probs.max(dim=-1)

    # Determine thresholds
    if thresholds is None:
        thresholds = {}
    elif isinstance(thresholds, (int, float)):
        t = float(thresholds)
        thresholds = {feat: t for feat in ["pos"] + FEATURE_ORDER}

    results = []
    seen = set()

    for token_idx, word_id in enumerate(word_ids):
        if word_id is None or word_id in seen:
            continue
        seen.add(word_id)

        pos_idx = pos_pred[token_idx].item()
        pos_confidence = pos_conf[token_idx].item()
        pos_str = id2label_all["pos"][pos_idx]
        pos_threshold = thresholds.get("pos", 0.0)

        result = {
            "word": sentence_words[word_id],
            "pos": {
                "label": pos_str,
                "confidence": round(pos_confidence, 4),
                "needs_fallback": pos_confidence < pos_threshold,
                "probabilities": {id2label_all["pos"][i]: round(p, 4)
                                  for i, p in enumerate(pos_probs[token_idx].cpu().tolist())
                                  if p > 0.01},  # only show probs > 1%
            },
        }

        for feat_idx, feat in enumerate(FEATURE_ORDER):
            if pos_mask_tensor[pos_idx, feat_idx].item():
                feat_logit = feature_logits[feat][0, token_idx]  # (num_labels,)


                feat_probs = F.softmax(feat_logit, dim=-1)
                feat_conf, feat_pred_idx = feat_probs.max(dim=-1)

                feat_confidence = feat_conf.item()
                feat_threshold = thresholds.get(feat, 0.0)

                result[feat] = {
                    "label": id2label_all[feat][feat_pred_idx.item()],
                    "confidence": round(feat_confidence, 4),
                    "needs_fallback": feat_confidence < feat_threshold,
                    "applicable": True,
                    "probabilities": {id2label_all[feat][i]: round(p, 4)
                                      for i, p in enumerate(feat_probs.cpu().tolist())
                                      if p > 0.01},
                }
            else:
                result[feat] = {
                    "label": "—",
                    "confidence": None,
                    "needs_fallback": False,
                    "applicable": False,
                }

        results.append(result)

    return results

