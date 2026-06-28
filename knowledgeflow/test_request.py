import asyncio
from notion_client import AsyncClient
import os

async def main():
    client = AsyncClient(auth=os.environ.get('NOTION_TOKEN', 'your_token_here'))
    db_id = '157cbe09-da83-4d6c-9b75-2b5fead43447'
    try:
        res = await client.request(
            path=f'databases/{db_id}/query',
            method='POST',
            body={'page_size': 1}
        )
        print('SUCCESS', len(res.get('results', [])))
    except Exception as e:
        print('ERROR1:', str(e))

    try:
        res = await client.request(
            path=f'/databases/{db_id}/query',
            method='POST',
            body={'page_size': 1}
        )
        print('SUCCESS', len(res.get('results', [])))
    except Exception as e:
        print('ERROR2:', str(e))
        
    try:
        res = await client.request(
            path=f'/v1/databases/{db_id}/query',
            method='POST',
            body={'page_size': 1}
        )
        print('SUCCESS', len(res.get('results', [])))
    except Exception as e:
        print('ERROR3:', str(e))
