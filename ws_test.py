import asyncio

import aiohttp


async def main():
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(
            "wss://api-realtime-sandbox.p2pquake.net/v2/ws"
        ) as ws:
            print("Connected")
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    print(msg.json())
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break


if __name__ == "__main__":
    asyncio.run(main())
