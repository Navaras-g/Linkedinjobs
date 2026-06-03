import json
from pathlib import Path

raw = Path('cookies.json').read_text(encoding='utf-8').strip()
cookies = json.loads(raw)
print(f'Total cookies: {len(cookies)}')
print(f'Type: {type(cookies)}')

important = ['li_at', 'JSESSIONID', 'liap', 'li_rm']
found = [c['name'] for c in cookies if c['name'] in important]
print(f'Auth cookies found: {found}')
print(f'Cookie fields: {list(cookies[0].keys())}')