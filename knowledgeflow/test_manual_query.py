import asyncio
import os
from notion_client import AsyncClient

async def main():
    client = AsyncClient(auth=os.environ.get('NOTION_TOKEN', 'your_token_here'))
    db_id = '157cbe09-da83-4d6c-9b75-2b5fead43447'
    try:
        res = await client.request(
            path=f'databases/{db_id}/query',
            method='POST',
            body={'page_size': 1}
        )
        print('SUCCESS')
        print(len(res.get('results', [])))
    except Exception as e:
        print('ERROR:', str(e))

asyncio.run(main())
