import sys
import asyncio
import websockets
import json
from urllib.parse import urlencode
from diskcache import Cache
from osint.adapter import QueryLogic
from osint.services.query_repo import load_active_query_logic
from utils.env import load_environment, make_sqlalchemy_url
from osint.utils.query_matcher import extract_matching_terms
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
import re

load_environment(prod=True)
engine = create_async_engine(make_sqlalchemy_url(), echo=False)
db_session = async_sessionmaker(engine, expire_on_commit=False)
cache = Cache('cache_bluesky') ### instantiate cache at the class level

class Jetstream:
    def __init__(self, endpoint="jetstream1.us-east.bsky.network"):
        self.endpoint = endpoint
        self.emitters = {}
        self.ws = None

    @property
    def url(self):
        params = [("wantedCollections", collection) for collection in self.emitters.keys()]
        query = urlencode(params)
        return f"wss://{self.endpoint}/subscribe?{query}"

    def _listen(self, collection, operation, listener):
        self.emitters.setdefault(collection, {}).setdefault(operation, []).append(listener)

    def on_create(self, collection, listener):
        self._listen(collection, "create", listener)

    async def start(self):
        if self.ws:
            await self.ws.close()
        self.ws = await websockets.connect(self.url, ping_interval=None)
        async for message in self.ws:
            data = json.loads(message)
            if data.get("kind") != "commit":
                continue
            commit = data.get("commit", {})
            collection = commit.get("collection")
            operation = commit.get("operation")
            if not collection or not operation:
                continue
            for listener in self.emitters.get(collection, {}).get(operation, []):
                await listener(data)


async def handle_bluesky_post(event):

    commit = event.get('commit', {})
    text = commit.get("record", {}).get("text")

    # Load entity/action terms from DB
    async with db_session() as sess:
        queries: QueryLogic = await load_active_query_logic(sess)
        if not queries:
            print("No ENABLED queries found in the database; exiting.")
            return

        def clean_terms(terms):
            # Strips straight and curly single/double quotes from both ends
            return [re.sub(r'^[\'"“”‘’]+|[\'"“”‘’]+$', '', t.strip()).lower() for t in terms]

        if text:
            text = text.lower()
            for qid, (entity_terms, action_terms) in queries.items():
                entity_terms = clean_terms(entity_terms)
                action_terms = clean_terms(action_terms)
                matches = extract_matching_terms(text, entity_terms, action_terms)
                if len(matches) > 0:
                    print(f"matches={matches}")
                if matches:
                    # cache = Cache('cache_bluesky') ### instantiate cache at the class level
                    unique_id = commit.get('cid') or commit.get('rkey') or str(hash(json.dumps(event)))
                    cache.set(
                        unique_id,
                        {
                            "event": event,
                            "text": text,
                            "qid": qid,
                            "matches": matches
                        },
                        expire=60*60*24
                    )
                    # cache.close()
                    print(f"Cached matching entry: {unique_id}, text: {text}, qid: {qid}, matches: {matches}")



async def main():
    js = Jetstream()
    js.on_create("app.bsky.feed.post", lambda event: asyncio.create_task(handle_bluesky_post(event)))

    await js.start()

    # If js.start() spawns a task and exits, keep this coroutine alive
    while True:
        await asyncio.sleep(30)  # sleep an hour at a time, indefinitely

    # task = asyncio.create_task(js.start())

    # await asyncio.sleep(120) # run for 5 seconds; adjust as needed

    # if js.ws:

    # await js.ws.close()

    # task.cancel()




if __name__ == "__main__":
    asyncio.run(main())