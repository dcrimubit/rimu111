from typing import TYPE_CHECKING, Any, MutableMapping

import pyrogram

from .. import command, module, util
from .base import Base

if TYPE_CHECKING:
    from .bot import Bot


class CommandDispatcher(Base):
    commands: MutableMapping[str, command.Command]

    def __init__(self: "Bot", **kwargs: Any) -> None:
        self.commands = {}

        super().__init__(**kwargs)

    def register_command(self: "Bot", mod: module.Module, name: str,
                         func: command.CommandFunc) -> None:
        cmd = command.Command(name, mod, func)

        if name in self.commands:
            orig = self.commands[name]
            raise module.ExistingCommandError(orig, cmd)

        self.commands[name] = cmd

        for alias in cmd.aliases:
            if alias in self.commands:
                orig = self.commands[alias]
                raise module.ExistingCommandError(orig, cmd, alias=True)

            self.commands[alias] = cmd

    def unregister_command(self: "Bot", cmd: command.Command) -> None:
        del self.commands[cmd.name]

        for alias in cmd.aliases:
            try:
                del self.commands[alias]
            except KeyError:
                continue

    def register_commands(self: "Bot", mod: module.Module) -> None:
        for name, func in util.misc.find_prefixed_funcs(mod, "cmd_"):
            done = False

            try:
                self.register_command(mod, name, func)
                done = True
            finally:
                if not done:
                    self.unregister_commands(mod)

    def unregister_commands(self: "Bot", mod: module.Module) -> None:
        to_unreg = []

        for name, cmd in self.commands.items():
            if name != cmd.name:
                continue

            if cmd.module == mod:
                to_unreg.append(cmd)

        for cmd in to_unreg:
            self.unregister_command(cmd)

    async def on_command(self: "Bot", client: pyrogram.Client,
                         message: pyrogram.types.Message) -> None:
        cmd = None

        try:
            try:
                cmd = self.commands[message.command[0]]
            except KeyError:
                return

            ctx = command.Context(self, message, len(message.command))

            try:
                ret = await cmd.func(ctx)

                if ret is not None:
                    await ctx.respond(ret)
            except pyrogram.errors.MessageNotModified:
                cmd.module.log.warning(
                    f"Command '{cmd.name}' triggered a message edit with no changes"
                )
            except Exception as E:
                cmd.module.log.error(f"Error in command '{cmd.name}'",
                                     exc_info=E)
                await ctx.respond(
                    f"?????? Error executing command:\n```{util.error.format_exception(E)}```"
                )

            await self.dispatch_event("command", cmd, message)
        except Exception as E:
            if cmd is not None:
                cmd.module.log.error("Error in command handler", exc_info=E)

            await self.respond(
                message,
                f"?????? Error in command handler:\n```{util.error.format_exception(E)}```",
            )
