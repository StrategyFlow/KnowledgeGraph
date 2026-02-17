import asyncio
import redis.asyncio as redis

class RedisClient:
    def __init__(self, host='localhost', port=6379, db=0):
        self.r = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True
        )

    async def publish(self, channel: str, message: str):
        await self.r.publish(channel, message)

    async def subscribe(self, channel: str, callback):
        async with self.r.pubsub() as pubsub:
            await pubsub.subscribe(channel)
            print(f"Subscribed to channel: {channel}")
            future = asyncio.create_task(self.reader(pubsub, callback))
            await future

    async def reader(self, channel: redis.client.PubSub, callback):
        while True:
            message = await channel.get_message(ignore_subscribe_messages=True, timeout=None)
            if message is not None:
                channel_name = message.get("channel", channel)
                print(f"[{channel_name}] Message Received: {message}")
                await callback(message["data"])

    async def close(self):
        await self.r.aclose()
