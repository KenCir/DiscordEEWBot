import asyncio
import logging
import os
import traceback
from datetime import datetime

import aiohttp
import discord
from discord import app_commands
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
        self.logger = logging.getLogger("p2pquake")
        self.latest_quake_data = None

        self.should_reconnect = True
        self.retry_count = 0
        self.max_retries = 5  # 5回までは即再接続
        self.retry_interval = 5  # 失敗時の最低待機秒数
        self.cooldown_wait = 300  # 5回連続失敗したら5分休む（300秒）

    async def cog_load(self) -> None:
        self.bot.loop.create_task(self.listen_p2pquake())

    async def cog_unload(self) -> None:
        self.should_reconnect = False  # ユーザー操作による unload → 再接続しない
        if self.ws is not None:
            await self.ws.close()

    async def connect_websocket(self, session):
        """WebSocket接続処理（リトライ制御あり）"""

        while self.should_reconnect:
            try:
                self.logger.info("Trying to connect to P2P WebSocket...")
                # ws = await session.ws_connect(
                #      "wss://api-realtime-sandbox.p2pquake.net/v2/ws",
                #    proxy=os.environ.get("PROXY_URL"),
                # )
                ws = await session.ws_connect(
                    "https://api.p2pquake.net/v2/ws",
                    proxy=os.environ.get("PROXY_URL"),
                )
                self.logger.info("P2P WebSocket Connected")
                self.retry_count = 0  # 成功したらリセット
                return ws

            except Exception:
                self.retry_count += 1
                self.logger.error("WebSocket connection failed:")
                self.logger.error(traceback.format_exc())

                # 最大リトライ回数を超えたら数分待機
                if self.retry_count > self.max_retries:
                    wait_time = self.cooldown_wait
                    self.logger.warning(
                        f"Too many retries. Waiting {wait_time} seconds before retrying..."
                    )
                else:
                    wait_time = self.retry_interval

                await asyncio.sleep(wait_time)

        return None  # should_reconnect が False の場合

    async def listen_p2pquake(self):
        await self.bot.wait_until_ready()

        async with aiohttp.ClientSession() as session:
            while self.should_reconnect:
                ws = await self.connect_websocket(session)
                if ws is None:
                    break

                self.ws = ws

                try:
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = msg.json()

                            # 重複除外
                            data_id = data.get("_id")
                            if data_id == self.latest_quake_data:
                                continue
                            self.latest_quake_data = data_id

                            match data["code"]:
                                case 551:
                                    await self.on_jma_quake(data)
                                case 552:
                                    await self.on_jma_tunami(data)
                                case 556:
                                    await self.on_jma_eew(data)
                                case _:
                                    pass

                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            raise aiohttp.ClientConnectionError()

                except asyncio.CancelledError:
                    # cog_unload → Cancelled → 再接続しない
                    self.logger.info("listen_p2pquake task cancelled.")
                    break

                except Exception:
                    if self.should_reconnect:
                        self.logger.error("Unexpected error. Reconnecting...")
                        self.logger.error(traceback.format_exc())
                        await asyncio.sleep(1)  # 少し待って再接続
                        continue
                    else:
                        break

            self.logger.info("P2P WebSocket Disconnected")

    async def on_jma_quake(self, data) -> None:
        self.latest_quake_data = data
        embeds = []
        embed = discord.Embed(
            title=f"地震情報({format_issue_type(data['issue']['type'])})",
            description=f"{data['earthquake']['time']}頃、{f'{data["earthquake"]["hypocenter"]["name"]}で' if data['earthquake']['hypocenter']['name'] else ''}最大震度"
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

        channel_id = int(os.environ.get("QUAKE_NOTICE_CHANNEL_ID"))
        role_id = int(os.environ.get("QUAKE_NOTICE_ROLE_ID"))
        await self.bot.get_channel(channel_id).send(
            content=f"<@&{role_id}>", embeds=embeds
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

        channel_id = int(os.environ.get("TUNAMI_NOTICE_CHANNEL_ID"))
        role_id = int(os.environ.get("TUNAMI_NOTICE_ROLE_ID"))
        await self.bot.get_channel(channel_id).send(
            content=f"<@&{role_id}>", embed=embed
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

        channel_id = int(os.environ.get("EEW_NOTICE_CHANNEL_ID"))
        role_id = int(os.environ.get("EEW_NOTICE_ROLE_ID"))
        await self.bot.get_channel(channel_id).send(
            content=f"<@&{role_id}>", embed=embed
        )

    @app_commands.command(name="quake-info", description="最新の地震情報を表示します")
    async def quake_info(self, interaction: discord.Interaction):
        data = self.latest_quake_data
        if data is None:
            await interaction.response.send_message("No Data")
            return

        embed = discord.Embed(
            title=f"地震情報({format_issue_type(data['issue']['type'])})",
            description=f"{data['earthquake']['time']}頃、{f'{data["earthquake"]["hypocenter"]["name"]}で' if data['earthquake']['hypocenter']['name'] else ''}最大震度"
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

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(P2PQuake(bot))
