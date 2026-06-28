import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
from notion_client import Client
import os

client = Client(auth=os.environ.get('NOTION_TOKEN', 'your_token_here'))
db_id = '63cf61a3-7281-45d5-ad24-4939b96438cd'

try:
    res = client.databases.update(
        database_id=db_id,
        properties={
            'Name': {'name': 'Title'},
            'URL': {'url': {}}
        }
    )
    print(json.dumps(res['properties'], indent=2))
except Exception as e:
    print('ERROR:', str(e))
