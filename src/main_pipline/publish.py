from dotenv import load_dotenv
import asyncio
import contextlib
import os

from main_pipline.redis_client import RedisClient

async def listen_for_messages(client: RedisClient, channel: str, stop_event: asyncio.Event):
    async def handle_message(message: str):
        if not stop_event.is_set():
            print(f"[{channel}] {message}")

    await client.subscribe(channel, handle_message)

async def main():
    # load environment variables
    load_dotenv()

    # connect to redis
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    client = RedisClient(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    SEND_TO = "ie_request"
    LISTEN_TO = "ie_response"

    # subscribe to response channel in background
    stop_event = asyncio.Event()
    listener_task = asyncio.create_task(listen_for_messages(client, LISTEN_TO, stop_event))

    print("Type messages to publish. Type 'exit' or 'quit' or 'Ctrl+D' to stop.")
    try:
        while True:
            user_input = await asyncio.to_thread(input, "> ")
            message = user_input.strip()
            if not message:
                continue
            if message.lower() in {"exit", "quit"}:
                break
            await client.publish(SEND_TO, message)
            print(f"Published to channel {SEND_TO}: {message}")
    except (KeyboardInterrupt, EOFError):
        print("Shutting down...")
    finally:
        stop_event.set()
        listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listener_task
        await client.close()

def run():
    asyncio.run(main())

if __name__ == "__main__":
    run()
