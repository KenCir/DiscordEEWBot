from datetime import datetime

import aiohttp
import discord
from discord.ext import commands
from main import DiscordEEWBot


class P2P(commands.Cog):
    def __init__(self, bot: DiscordEEWBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                "wss://api-realtime-sandbox.p2pquake.net/v2/ws"
            ) as ws:
                print("P2P WebSocket Connected")
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = msg.json()
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        break
                    elif msg.type == aiohttp.WSMsgType.CLOSE:
                        break

                    print(data)
                    if data["code"] == 551:  # JMAQuake
                        embed = discord.Embed(
                            title=f"地震情報",
                            timestamp=datetime.strptime(
                                data["time"], "%Y/%m/%d %H:%M:%S.%f"
                            ),
                        )
                        embed.set_footer(
                            text=f"{data['issue']['source']}が{data['issue']['time']}に発表しました | {data['issue']['type']}"
                        )
                        await self.bot.get_channel(972836497747226654).send(embed=embed)

                await ws.close()


async def setup(bot):
    await bot.add_cog(P2P(bot))
