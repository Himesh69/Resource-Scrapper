from notion_client import AsyncClient
client = AsyncClient()
def find_methods(obj, name):
    for attr in dir(obj):
        if 'query' in attr:
            print(f"{name}.{attr}")
find_methods(client, 'client')
find_methods(client.databases, 'client.databases')
find_methods(client.search, 'client.search')
find_methods(client.pages, 'client.pages')
find_methods(client.blocks, 'client.blocks')
