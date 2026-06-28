from notion_client import AsyncClient
client = AsyncClient()
print(hasattr(client.databases, 'query'))
print(hasattr(client.databases, 'query_a_database'))
print(dir(client.databases))
