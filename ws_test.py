import asyncio

import aiohttp


async def main():
    async with aiohttp.ClientSession() as session:
        # https://api.p2pquake.net/v2/ws
        # wss://api-realtime-sandbox.p2pquake.net/v2/ws
        async with session.ws_connect("https://api.p2pquake.net/v2/ws") as ws:
            print("Connected")
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    print(msg.json())
                elif (
                    msg.type == aiohttp.WSMsgType.ERROR
                    or msg.type == aiohttp.WSMsgType.CLOSE
                ):
                    break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting...")
