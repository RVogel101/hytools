import sys, pkgutil
print('sys.path[0]:', sys.path[0])
import hytools
print('hytools.__file__=', hytools.__file__)
print('hytools package path:', hytools.__path__)
print('ingestion found:', 'hytools.ingestion' in sys.modules)
import importlib
try:
    m = importlib.import_module('hytools.ingestion._shared.helpers')
    print('helpers module file:', getattr(m, '__file__', None))
except Exception as e:
    print('ERROR importing helpers:', type(e), e)
print('Listing hytools.ingestion package contents:')
import hytools.ingestion as ing
print(list(pkgutil.iter_modules(ing.__path__)))
