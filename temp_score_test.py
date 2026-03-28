from hytools.linguistics.dialect.branch_dialect_classifier import (
    compute_wa_score,
    classify_text_classification,
)
texts = [
    'Ան կու գայ և մեծ շտապում ունի',
    'Մեզի մէջ տունը ճամբարը սկսաւ',
    'Նա այլեւս չըսեր այս ոճը',
    'Խաղալու ժամանակը միշտ ուրախ է',
    'Շատ լաւ մեծ մարդը պատմեց',
]
for t in texts:
    score = compute_wa_score(t)
    print(t, score, classify_text_classification(t)['label'])
