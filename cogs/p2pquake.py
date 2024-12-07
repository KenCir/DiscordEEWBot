from datetime import datetime

import aiohttp
import discord
from discord.ext import commands
from main import DiscordEEWBot


def format_issue_type(issue_type: str) -> str:
    """
    発表種類を変換する
    :param issue_type:
    :return:
    """

    match issue_type:
        case "ScalePrompt":
            return "震度速報"
        case "Destination":
            return "震源に関する情報"
        case "ScaleAndDestination":
            return "震度・震源に関する情報"
        case "DetailScale":
            return "各地の震度に関する情報"
        case "Foreign":
            return "遠地地震に関する情報"
        case "Other":
            return "その他の情報"
        case _:
            return "不明"


def format_issue_correct(correct: str) -> str:
    """
    訂正情報を変換する
    :param correct:
    :return:
    """

    match correct:
        case "None":
            return ""
        case "Unknown":
            return "訂正情報不明"
        case "ScaleOnly":
            return "震度情報の訂正が含まれます"
        case "DestinationOnly":
            return "震源情報の訂正が含まれます"
        case "ScaleAndDestination":
            return "震度・震源情報の訂正が含まれます"
        case _:
            return "訂正情報不明"


def format_earthquake_scale(scale: int) -> str:
    """
    震度を変換する
    :param scale:
    :return:
    """

    match scale:
        case -1:
            return "調査中"
        case 10:
            return "1"
        case 20:
            return "2"
        case 30:
            return "3"
        case 40:
            return "4"
        case 45:
            return "5弱"
        case 50:
            return "5強"
        case 55:
            return "6弱"
        case 60:
            return "6強"
        case 70:
            return "7"
        case _:
            return "不明"


def format_earthquake_depth(depth: int) -> str:
    """
    震源の深さを変換する
    :param depth:
    :return:
    """

    match depth:
        case -1:
            return "調査中"
        case 0:
            return "ごく浅い"
        case _:
            return f"{depth}km"


def format_earthquake_magnitude(magnitude: int) -> str:
    """
    マグニチュードを変換する
    :param magnitude:
    :return:
    """

    match magnitude:
        case -1:
            return "調査中"
        case _:
            return f"{magnitude}"


def format_earthquake_tsunami(tsunami: str) -> str:
    """
    津波情報を変換する
    :param tsunami:
    :return:
    """

    match tsunami:
        case "None":
            return "無し"
        case "Unknown":
            return "不明"
        case "Checking":
            return "調査中"
        case "NonEffective":
            return "若干の海面変動が予想されるが、被害の心配なし"
        case "Watch":
            return "津波注意報"
        case "Warning":
            return "津波予報(種類不明)"
        case _:
            return "不明"


def format_points(points: list) -> discord.Embed:
    """
    各地の震度情報を変換する
    :param points:
    :return:
    """

    scales = [
        {"scale": 70, "name": "震度7"},
        {"scale": 60, "name": "震度6強"},
        {"scale": 55, "name": "震6弱"},
        {"scale": 50, "name": "震度5強"},
        {"scale": 46, "name": "震度5弱以上と推定されるが震度情報を入手していない"},
        {"scale": 45, "name": "震度5弱"},
        {"scale": 40, "name": "震度4"},
        {"scale": 30, "name": "震度3"},
        {"scale": 20, "name": "震度2"},
        {"scale": 10, "name": "震度1"},
    ]
    embed = discord.Embed(title="各地の震度情報")

    for scale in scales:
        filtered_points = list(filter(lambda x: x["scale"] == scale["scale"], points))
        if len(filtered_points) > 0:
            embed.add_field(
                name=scale["name"],
                value=", ".join(map(lambda point: point["addr"], filtered_points)),
                inline=False,
            )

    return embed


class P2PQuake(commands.Cog):
    def __init__(self, bot: DiscordEEWBot):
        self.bot = bot
        self.ws = None

    async def cog_load(self) -> None:
        if self.bot.is_ready():
            self.bot.loop.create_task(self.listen_p2p())

    async def cog_unload(self) -> None:
        if self.ws is not None:
            await self.ws.close()

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.loop.create_task(self.listen_p2p())

    async def listen_p2p(self):
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                "wss://api-realtime-sandbox.p2pquake.net/v2/ws"
            ) as ws:
                self.ws = ws
                print("P2P WebSocket Connected")

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = msg.json()
                        print(data)

                        if data["code"] == 551:
                            await self.on_jmaquake(data)
                    elif (
                        msg.type == aiohttp.WSMsgType.ERROR
                        or msg.type == aiohttp.WSMsgType.CLOSE
                    ):
                        break

                print("P2P WebSocket Disconnected")

    async def on_jmaquake(self, data) -> None:
        embeds = []
        embed = discord.Embed(
            title=f"地震情報({format_issue_type(data['issue']['type'])})",
            description=f"{data['earthquake']['time']}頃、{f"{data['earthquake']['hypocenter']['name']}で" if data['earthquake']['hypocenter']['name'] else ''}最大震度"
            f"{format_earthquake_scale(data['earthquake']['maxScale'])}の地震がありました\n{format_issue_correct(data['issue']['correct'])}",
            timestamp=datetime.strptime(data["time"], "%Y/%m/%d %H:%M:%S.%f"),
        )
        embed.add_field(
            name="最大震度",
            value=format_earthquake_scale(data["earthquake"]["maxScale"]),
            inline=False,
        )
        embed.add_field(
            name="発生時刻",
            value=f"{data['earthquake']['time']}頃",
            inline=False,
        )
        embed.add_field(
            name="震源地",
            value=data["earthquake"]["hypocenter"]["name"] or "調査中",
            inline=False,
        )
        embed.add_field(
            name="深さ",
            value=format_earthquake_depth(data["earthquake"]["hypocenter"]["depth"]),
            inline=False,
        )
        embed.add_field(
            name="マグニチュード",
            value=format_earthquake_magnitude(
                data["earthquake"]["hypocenter"]["magnitude"]
            ),
            inline=False,
        )
        embed.add_field(
            name="津波の有無",
            value=format_earthquake_tsunami(data["earthquake"]["domesticTsunami"]),
            inline=False,
        )
        embed.set_footer(
            text=f"P2P地震情報 | {data['issue']['source']}が{data['issue']['time']}に発表しました"
        )
        embeds.append(embed)
        if len(data["points"]) > 0:
            embeds.append(format_points(data["points"]))

        await self.bot.get_channel(972836497747226654).send(embeds=embeds)


async def setup(bot):
    await bot.add_cog(P2PQuake(bot))
