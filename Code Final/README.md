# Project Code

## Directory Structure

```
Code Final/
├── models_definitions/     # Model definitions and inference logic
├── model_notebooks/        # Training and evaluation notebooks (Colab)
├── web/                    # Flask application and frontend
├── model_weights/          # Trained model weights and configs
├── data/                   # Datasets, generation scripts, and raw sources
└── config/                 # Runtime configuration files
```

### `models_definitions/`

Reusable Python modules imported by both the notebooks (for training) and the web app (for inference). No training logic, only definitions and prediction functions.

- `morph_constants.py` — shared constants: `FEATURE_ORDER`, `IGNORE_INDEX`, `POS_FEATURE_MASK`, `MORPH_POSITIONS`, and label mappings. Single source of truth for values previously duplicated across notebooks and `app.py`.
- `morphological_analyser.py` — model architecture: `LatinMorphologicalAnalyser` (custom `PreTrainedModel` with POS head + POS-conditioned feature heads), its config class, and the `predict_with_confidence` function.
- `intent_classifier.py` — thin wrapper around `BertForSequenceClassification` with a prediction helper.
- `inference.py` — high-level service classes (`MorphAnalyserService`, `IntentClassifierService`) that handle model loading, tokeniser setup, and expose a clean API for the web app.
- `data_processing.py` — data pipeline utilities shared by training notebooks: `Token`/`Sentence` dataclasses, PROIEL XML parser, morphology decoder, label vocabulary builder, tokenisation alignment, and the custom `MultiLabelDataCollator`.

### `model_notebooks/`

Jupyter notebooks for training, evaluation, and analysis. Each notebook imports from `models_definitions/` rather than redefining classes. Designed to run on Google Colab with GPU.

- `01_morph_train.ipynb` — two-phase training of the morphological analyser (frozen BERT → full fine-tuning) on the PROIEL treebank.
- `02_morph_evaluate.ipynb` — per-feature classification reports, confusion matrices, and test-set metrics.
- `03_morph_threshold.ipynb` — confidence calibration analysis: reliability diagrams, accuracy-vs-coverage curves, and per-feature threshold selection.
- `04_intent_train.ipynb` — fine-tuning `bert-base-uncased` for intent classification on the generated question dataset.
- `05_intent_evaluate.ipynb` — intent classifier evaluation: confusion matrix, classification report.

### `web/`

The Flask web application and chat frontend.

- `app.py` — Flask server. Imports service classes from `models/inference.py`, loads weights from `saved_models/`, and exposes `/chat` endpoint.
- `templates/index.html` — chat interface with sidebar, theme toggle, conversation management.
- `static/styles.css` — dark/light theme styles, responsive layout, sidebar collapse/drawer.
- `static/scripts.js` — chat session management (localStorage), message sending, sidebar rendering, export modal.

### `model_weights/`

Trained model weights, tokeniser files, and config JSONs.

```
model_weights/
├── morphological_analyser/
│   ├── config.json
│   ├── model.safetensors
│   ├── tokenizer_config.json
│   ├── vocab.txt
│   └── special_tokens_map.json
├── intent_classifier/
│   ├── config.json
│   ├── model.safetensors
│   └── tokenizer files...
└── latin_bert/               # Pre-trained Latin BERT base (needed to initialise the morph analyser)
```

### `data/`

Raw source data, dataset generation scripts, and generated training sets.

```
data/
├── raw/
│   ├── latin-nt.xml              # PROIEL treebank (morph analyser training data)
│   └── question_templates.json   # Intent question templates and placeholder values
├── generated/
│   ├── words_data.csv            # Latin word forms with morphological features
│   └── intent_data.csv           # Generated intent classification training set
└── scripts/
    ├── words_new.py              # Interface to Whitaker's Words program
    ├── words_dataset.py          # Extracts word forms and features via Whitaker's Words
    └── build_dataset.py          # Combines word data with question templates to produce intent_data.csv
```

The data generation pipeline runs `words_dataset.py` → `words_data.csv` → `build_dataset.py` → `intent_data.csv`. This only needs to run once before training the intent classifier.

### `config/`

Runtime configuration loaded by the web app at startup.

- `thresholds.json` — per-feature confidence thresholds for the morphological analyser's fallback mechanism, derived from the analysis in `03_morph_threshold.ipynb`.
- `pos_feature_mask.json` — POS-to-feature compatibility matrix defining which morphological features are applicable for each part of speech.

