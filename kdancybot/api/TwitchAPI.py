from kdancybot.Token import TwitchToken
from kdancybot.Message import Message
from kdancybot.Commands import Commands
from kdancybot.Timer import Timer
from kdancybot.Cooldown import Cooldown

import websockets
import re
import logging
from concurrent.futures import ThreadPoolExecutor
import asyncio
import traceback


def parse_beatmap_link(message):
    patterns = {
        "official": r"osu.ppy.sh\/beatmapsets\/[0-9]+\#(osu|taiko|fruits|mania)\/(?P<map_id>[0-9]+)",
        "official_alt": r"osu.ppy.sh\/beatmaps\/(?P<map_id>[0-9]+)",
        "old_single": r"(osu|old).ppy.sh\/b\/(?P<map_id>[0-9]+)",
    }

    for link_type, pattern in patterns.items():
        result = re.search(pattern, message)

        # If there is no match, search for old beatmap link
        if result is None:
            continue
        else:
            return result["map_id"]

    return None


class TwitchChatHandler:
    def __init__(self, config: dict):
        self.config = config
        self.token = TwitchToken(config)
        self.commands = Commands(config)
        self.url = "ws://irc-ws.chat.twitch.tv:80"
        self.username = "kdancybot"
        self.ignored_users = [self.username, "nightbot", "streamelements"]
        self.command_templates = {
            "r": self.commands.recent,
            "recent": self.commands.recent,
            "rb": self.commands.recentbest,
            "recentbest": self.commands.recentbest,
            "tb": self.commands.todaybest,
            "todaybest": self.commands.todaybest,
            "ppdiff": self.commands.ppdiff,
            "whatif": self.commands.whatif,
            "top": self.commands.top,
        }

        self.cd = Cooldown(self.command_templates.keys(), config["users"].keys())
        self.executor = ThreadPoolExecutor(20)

    async def respond_to_message(self, ws, message, ret):
        if ret:
            await ws.send(
                "@reply-parent-msg-id={} PRIVMSG #{} :{}".format(
                    message.tags.get("id", 0), message.channel, ret
                )
            )

    async def handle_requests(self, ws, message):
        if message.user.lower() not in self.ignored_users:
            map_id = parse_beatmap_link(message.message)
            if map_id and self.cd.cd("request", message.channel):
                ret = await asyncio.get_event_loop().run_in_executor(
                    self.executor, self.commands.req, message, map_id
                )
                await self.respond_to_message(ws, message, ret)

    async def handle_commands(self, ws, message: Message):
        if message and message.user_command:
            command_func = self.command_templates.get(message.user_command)
            if command_func and self.cd.cd(message.user_command, message.channel):
                ret = await asyncio.get_event_loop().run_in_executor(
                    self.executor, command_func, message
                )
                await self.respond_to_message(ws, message, ret)

    async def handle_privmsg(self, ws, message):
        # await asyncio.gather(
        #     self.handle_requests(ws, message), self.handle_commands(ws, message)
        # )
        if not self.config["ignore_requests"].get(message.channel):
            await self.handle_requests(ws, message)
        if not self.config["ignore_commands"].get(message.channel):
            await self.handle_commands(ws, message)

    async def handle_message(self, ws, message):
        try:
            if message.type == "PRIVMSG":
                await self.handle_privmsg(ws, message)
        except Exception as e:
            logging.warning(traceback.format_exc())
            # logging.warning(e)

    async def login(self, ws):
        token = await asyncio.get_event_loop().run_in_executor(
            self.executor, self.token.token
        )
        await ws.send("CAP REQ :twitch.tv/membership twitch.tv/tags twitch.tv/commands")
        await ws.send("PASS oauth:{}".format(token))
        await ws.send("NICK {}".format(self.username))

    async def join_channels(self, ws):
        join_message = "JOIN #" + ",#".join(
            [channel for channel in self.config["users"].keys()]
        )
        await ws.send(join_message)

    async def loop(self):
        async for ws in websockets.connect(self.url):
            try:
                await self.login(ws)
                await self.join_channels(ws)
                logging.warning("Joined twitch chat!")
                while True:
                    msg = await ws.recv()
                    message = Message(msg)
                    await self.handle_message(ws, message)
            except websockets.exceptions.ConnectionClosed as e:
                logging.critical(e, traceback.format_exc())
                continue
            except Exception as e:
                logging.critical(e, traceback.format_exc())
                await asyncio.sleep(7.27)
                continue
