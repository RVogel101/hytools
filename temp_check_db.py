from scripts.external_db import get_db

db = get_db('config/settings.yaml')
print('collections:', db.list_collection_names())
coll = db.get_collection('external_datasets')
print('count:', coll.count_documents({}))
print('distinct tags (sample 50):')
print(list(coll.distinct('tag'))[:50])
