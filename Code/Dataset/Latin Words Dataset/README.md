# Latin Words Dataset

## Dependencies

Install all dependencies listed in [```requirements.txt```](/requirements.txt):

```bash
pip install -r requirements.txt
```

## Scripts

These scripts must be contained in the directory that contains the ```whitakers-words``` subdirectory (which contains the compiled Whitaker's Words program). Currently the paths are absolute paths.

[```words.py```](/words.py) - Class to interface with Whitaker's Words program.

[```words_dataset.py```](/words_dataset.py) - Script to extract additional morphological information from Whitaker's Words program to supplement missing information in the unimorph latin dataset.
