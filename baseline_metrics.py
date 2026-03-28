import json
from pathlib import Path
from hytools.ingestion._shared import helpers as h

def load():
    path = Path('tests/data/textbook_modern_wa_vocab_and_sentences.json')
    data = json.loads(path.read_text(encoding='utf-8'))
    return [(t,1) for t in data['sentences_western']], [(t,0) for t in data['sentences_eastern']]

def classify(text):
    r = h.classify_text_classification(text)
    if r['label'] == 'likely_western':
        return 'western'
    if r['label'] == 'likely_eastern':
        return 'eastern'
    return 'western' if h.compute_wa_score(text) >= 5.0 else 'eastern'

def metrics(dataset):
    tp=fp=fn=tn=0
    for t,l in dataset:
        p = classify(t)
        if l == 1:
            if p == 'western': tp += 1
            else: fn += 1
        else:
            if p == 'western': fp += 1
            else: tn += 1
    precision = tp/(tp+fp) if tp+fp else 0
    recall = tp/(tp+fn) if tp+fn else 0
    f1 = 2*precision*recall/(precision+recall) if precision+recall else 0
    return {'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':precision,'recall':recall,'f1':f1}

west,east=load()
train=west[:int(0.8*len(west))]+east[:int(0.8*len(east))]
valid=west[int(0.8*len(west)):]+east[int(0.8*len(east)):]
print('baseline train', metrics(train))
print('baseline valid', metrics(valid))
