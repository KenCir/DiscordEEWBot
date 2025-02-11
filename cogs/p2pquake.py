import traceback
from datetime import datetime

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from main import DiscordEEWBot

QUAKE_NOTICE_CHANNEL_ID = 1022180008762019931
QUAKE_NOTICE_ROLE_ID = 1329352490499571722
TUNAMI_NOTICE_CHANNEL_ID = 1329352412892499988
TUNAMI_NOTICE_ROLE_ID = 1329352555578396743
EEW_NOTICE_CHANNEL_ID = 1022179884384133170
EEW_NOTICE_ROLE_ID = 1329352085065568331


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


def format_earthquake_points(points: list) -> discord.Embed:
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
            self.bot.loop.create_task(self.listen_p2pquake())

    async def cog_unload(self) -> None:
        if self.ws is not None:
            await self.ws.close()

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.loop.create_task(self.listen_p2pquake())

    @app_commands.command(name="p2p-test")
    async def test(self, interaction: discord.Interaction):
        await interaction.response.send_message("Test")

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.p2pquake.net/v2/history?codes=552"
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    await self.on_jma_tunami(data[1])
                    await self.on_jma_tunami(data[0])

    async def listen_p2pquake(self):
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                # "wss://api-realtime-sandbox.p2pquake.net/v2/ws"
                "https://api.p2pquake.net/v2/ws"
            ) as ws:
                self.ws = ws
                print("P2P WebSocket Connected")

                try:
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = msg.json()
                            print(data)

                            match data["code"]:
                                case 551:  # 地震情報
                                    await self.on_jma_quake(data)
                                case 552:  # 津波予報
                                    await self.on_jma_tunami(data)
                                case 554:  # (緊急地震速報 発表検出)
                                    pass
                                case 555:  # (各地域ピア数)
                                    pass
                                case 556:  # 緊急地震速報(警報)
                                    await self.on_jma_eew(data)
                                case 561:  # 地震感知情報
                                    pass
                                case 9611:  # 地震感知情報 解析結果
                                    pass
                        elif (
                            msg.type == aiohttp.WSMsgType.ERROR
                            or msg.type == aiohttp.WSMsgType.CLOSE
                        ):
                            break
                except Exception as e:
                    print(traceback.format_exc())
                    await self.ws.close()
                    self.bot.loop.create_task(self.listen_p2pquake())

                print("P2P WebSocket Disconnected")

    async def on_jma_quake(self, data) -> None:
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
        if len(data["points"]) > 0 and data["earthquake"]["maxScale"] >= 30:
            embeds.append(format_earthquake_points(data["points"]))

        await self.bot.get_channel(QUAKE_NOTICE_CHANNEL_ID).send(
            content=f"<@&{QUAKE_NOTICE_ROLE_ID}>", embeds=embeds
        )

    async def on_jma_tunami(self, data) -> None:
        if data["cancelled"]:
            embed = discord.Embed(
                title="津波予報情報(解除)",
                description="先ほどの津波予報情報は解除されました",
                timestamp=datetime.strptime(data["time"], "%Y/%m/%d %H:%M:%S.%f"),
            )
            embed.set_footer(
                text=f"P2P地震情報 | {data['issue']['source']}が{data['issue']['time']}に発表しました"
            )
        else:
            grades = [
                {"grade": "MajorWarning", "name": "大津波警報"},
                {"grade": "Warning", "name": "津波警報"},
                {"grade": "Watch", "name": "津波注意報"},
                {"grade": "Unknown", "name": "不明"},
            ]
            embed = discord.Embed(
                title="津波予報情報",
                description=f"津波予報情報が発表されました",
                timestamp=datetime.strptime(data["time"], "%Y/%m/%d %H:%M:%S.%f"),
            )

            for grade in grades:
                filtered_areas = list(
                    filter(lambda x: x["grade"] == grade["grade"], data["areas"])
                )
                if len(filtered_areas) > 0:
                    embed.add_field(
                        name=grade["name"],
                        value=", ".join(map(lambda area: area["name"], filtered_areas)),
                        inline=False,
                    )

            embed.set_footer(
                text=f"P2P地震情報 | {data['issue']['source']}が{data['issue']['time']}に発表しました"
            )

        await self.bot.get_channel(TUNAMI_NOTICE_CHANNEL_ID).send(
            content=f"<@&{TUNAMI_NOTICE_ROLE_ID}>", embed=embed
        )

    async def on_jma_eew(self, data) -> None:
        if data.get("test", False):
            return

        if data["cancelled"]:
            embed = discord.Embed(
                title="緊急地震速報(取消)",
                description="先ほどの緊急地震速報は取り消されました",
                timestamp=datetime.strptime(data["time"], "%Y/%m/%d %H:%M:%S.%f"),
                color=discord.Color.blue(),
            )
        else:
            embed = discord.Embed(
                title="緊急地震速報(警報)",
                description="緊急地震速報が発表されました",
                timestamp=datetime.strptime(data["time"], "%Y/%m/%d %H:%M:%S.%f"),
                color=discord.Color.red(),
            )
            if data["earthquake"]["hypocenter"]["name"]:
                embed.add_field(
                    name="震源地",
                    value=data["earthquake"]["hypocenter"]["name"],
                    inline=False,
                )
                embed.add_field(
                    name="深さ",
                    value=format_earthquake_depth(
                        int(data["earthquake"]["hypocenter"]["depth"])
                    ),
                    inline=False,
                )
                embed.add_field(
                    name="マグニチュード",
                    value=format_earthquake_magnitude(
                        int(data["earthquake"]["hypocenter"]["magnitude"])
                    ),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="震源地",
                    value="不明",
                    inline=False,
                )

        embed.set_footer(text=f"P2P地震情報 | {data['issue']['time']}に発表しました")

        await self.bot.get_channel(EEW_NOTICE_CHANNEL_ID).send(
            content=f"<@&{EEW_NOTICE_ROLE_ID}>", embed=embed
        )


async def setup(bot):
    await bot.add_cog(P2PQuake(bot))
