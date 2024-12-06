import os

import discord
from discord import app_commands
from discord.ext import commands
from main import DiscordEEWBot


@app_commands.guild_only()
class DebugCommand(
    commands.GroupCog, name="debug", description="デバッグ関連のコマンド"
):
    def __init__(self, bot: DiscordEEWBot):
        super().__init__()
        self.bot = bot

    @app_commands.command(name="reload", description="Cogをリロードします")
    @app_commands.describe(resync="コマンドを再同期します")
    async def reload(self, interaction: discord.Interaction, resync: bool = False):
        await interaction.response.defer(ephemeral=True)

        for extension in self.bot.initial_extensions:
            await self.bot.reload_extension(extension)

        if resync:
            self.bot.tree.copy_global_to(
                guild=discord.Object(id=os.environ.get("GUILD_ID"))
            )
            await self.bot.tree.sync(
                guild=discord.Object(id=os.environ.get("GUILD_ID"))
            )
        await interaction.followup.send(
            f"Reloaded {'and Resync Command' if resync else ''}"
        )

    @app_commands.command(name="ping", description="Botのレイテンシを表示します")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"Pong! {self.bot.latency * 1000:.2f}ms",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(DebugCommand(bot))
