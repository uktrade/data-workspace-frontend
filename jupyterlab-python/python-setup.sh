python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r /root/requirements.txt
python3 -m spacy download en
python -m nltk.downloader -d /usr/local/share/nltk_data wordnet stopwords gutenberg
