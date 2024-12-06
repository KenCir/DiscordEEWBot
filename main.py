import os
import traceback

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


class DiscordEEWBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=(), help_command=None, intents=discord.Intents.default()
        )

        self.initial_extensions = ["cogs.debug", "cogs.p2p"]

    async def setup_hook(self) -> None:
        for extension in self.initial_extensions:
            await self.load_extension(extension)

        # self.tree.clear_commands()
        self.tree.copy_global_to(guild=discord.Object(id=os.environ.get("GUILD_ID")))
        await self.tree.sync(guild=discord.Object(id=os.environ.get("GUILD_ID")))

        self.tree.on_error = self.on_tree_error

    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def on_tree_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        print(f"ERROR: {interaction.command}\n{error}")
        print(traceback.format_exc())

        if isinstance(error, app_commands.CommandOnCooldown):
            msg = f"コマンドはクールダウン中です、**{error.retry_after:.2f}**秒後に再度お試しください"
        elif isinstance(error, app_commands.NoPrivateMessage):
            msg = "このコマンドはDMでは実行できません"
        elif isinstance(error, app_commands.MissingRole):
            missing_role = (
                error.missing_role
                if type(error.missing_role) is str
                else interaction.guild.get_role(error.missing_role)
            )
            msg = f"このコマンドを実行するためには`{missing_role}`ロールが必要です"
        elif isinstance(error, app_commands.MissingRole):
            missing_role = (
                error.missing_role
                if type(error.missing_role) is str
                else interaction.guild.get_role(error.missing_role)
            )
            msg = f"このコマンドを実行するためには`{missing_role}`ロールが必要です"
        elif isinstance(error, app_commands.MissingAnyRole):
            missing_roles = ", ".join(
                map(
                    lambda r: r if type(r) is str else interaction.guild.get_role(r),
                    error.missing_roles,
                )
            )
            msg = f"このコマンドを実行するためには`{missing_roles}`いずれかのロールが必要です"
        elif isinstance(error, app_commands.MissingPermissions):
            missing_permissions = ", ".join(error.missing_permissions)
            msg = f"このコマンドを実行するためには`{missing_permissions}`権限が必要です"
        elif isinstance(error, app_commands.BotMissingPermissions):
            missing_permissions = ", ".join(error.missing_permissions)
            msg = f"このコマンドを実行するためにはBotに`{missing_permissions}`権限が必要です"
        elif isinstance(error, app_commands.CheckFailure):
            msg = "このコマンドは実行できません"
        elif isinstance(error, app_commands.CommandInvokeError):
            msg = "エラーが発生しました"
        else:
            msg = "エラーが発生しました"

        if msg is not None:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)


def main():
    bot = DiscordEEWBot()
    bot.run(os.environ.get("DISCORD_TOKEN"))


if __name__ == "__main__":
    load_dotenv()
    main()
