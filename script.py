import logging
logging.basicConfig(level=logging.INFO)
from hytools.ingestion.acquisition import archive_org
cfg = {
    'database': {
        'mongodb_uri': 'mongodb://localhost:27017/',
        'mongodb_database': 'western_armenian_corpus'
    },
    'scraping': {
        'archive_org': {
            'max_results': 5,
            'queries': ['language:arm AND mediatype:texts']
        }
    }
}
print('Starting archive_org.run with test config...')
try:
    archive_org.run(cfg)
    print('archive_org.run completed')
except Exception as e:
    print('archive_org.run raised:', repr(e))
