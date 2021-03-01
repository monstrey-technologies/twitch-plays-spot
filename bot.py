import logging
import threading
import time

import irc.bot

from constants import MOVEMENT_BACKWARD, MOVEMENT_FORWARD, MOVEMENT_SIT, MOVEMENT_STAND, MOVEMENT_STRAFE_LEFT, \
    MOVEMENT_STRAFE_RIGHT, MOVEMENT_TURN_LEFT, MOVEMENT_TURN_RIGHT


class TwitchBot(irc.bot.SingleServerIRCBot):
    def __init__(self, username, client_id, token, channel, movement_callback):
        self.__client_id = client_id
        self.__token = token
        self.__channel = '#' + channel
        self.__chat_buffer = {}
        self.__chat_count = 0

        self.__movement_callback = movement_callback

        server = 'irc.chat.twitch.tv'
        port = 6667
        logging.info(f'Connecting to twitch-server {server} on port {port}...')
        irc.bot.SingleServerIRCBot.__init__(
            self, [(server, port, str(token))], username, username)

    def on_welcome(self, c, e):
        logging.info(f'Joining {self.__channel}')

        threading.Thread(target=self.__chat_analyzer).start()

        # You must request specific capabilities before you can use them
        c.cap('REQ', ':twitch.tv/membership')
        c.cap('REQ', ':twitch.tv/tags')
        c.cap('REQ', ':twitch.tv/commands')
        c.join(self.__channel)

    def get_chat_count(self):
        return self.__chat_count

    def on_pubmsg(self, c, e):
        # If a chat message starts with an exclamation point, try to run it as a command
        if e.arguments[0][:1] == '!':
            cmd = e.arguments[0].split(' ')[0][1:]
            self.do_command(e, cmd)
        return

    def do_command(self, event, cmd):
        moves = [MOVEMENT_BACKWARD, MOVEMENT_FORWARD, MOVEMENT_SIT, MOVEMENT_STAND,
                 MOVEMENT_STRAFE_LEFT, MOVEMENT_STRAFE_RIGHT, MOVEMENT_TURN_LEFT, MOVEMENT_TURN_RIGHT]
        if cmd == "help":
            self.connection.privmsg(event.target, ' '.join(
                [str(elem) for elem in map((lambda move: f"!{move}"), moves)]))

        if cmd in moves:
            self.__chat_buffer[event.source.nick] = cmd

    def __chat_analyzer(self):
        while True:
            time.sleep(1)

            chat_buffer = self.__chat_buffer
            self.__chat_count = len(self.__chat_buffer.keys()) if len(
                self.__chat_buffer.keys()) > 0 else self.__chat_count
            self.__chat_buffer = {}

            count_dict = {
                MOVEMENT_SIT: 0,
                MOVEMENT_STAND: 0,
                MOVEMENT_STRAFE_LEFT: 0,
                MOVEMENT_STRAFE_RIGHT: 0,
                MOVEMENT_TURN_LEFT: 0,
                MOVEMENT_TURN_RIGHT: 0,
                MOVEMENT_BACKWARD: 0,
                MOVEMENT_FORWARD: 0
            }

            for value in chat_buffer.values():
                if value == MOVEMENT_SIT:
                    count_dict[MOVEMENT_SIT] += 1
                elif value == MOVEMENT_STAND:
                    count_dict[MOVEMENT_STAND] += 1
                elif value == MOVEMENT_STRAFE_LEFT:
                    count_dict[MOVEMENT_STRAFE_LEFT] += 1
                elif value == MOVEMENT_STRAFE_RIGHT:
                    count_dict[MOVEMENT_STRAFE_RIGHT] += 1
                elif value == MOVEMENT_TURN_LEFT:
                    count_dict[MOVEMENT_TURN_LEFT] += 1
                elif value == MOVEMENT_TURN_RIGHT:
                    count_dict[MOVEMENT_TURN_RIGHT] += 1
                elif value == MOVEMENT_BACKWARD:
                    count_dict[MOVEMENT_BACKWARD] += 1
                elif value == MOVEMENT_FORWARD:
                    count_dict[MOVEMENT_FORWARD] += 1

            top_result = sorted(
                count_dict, key=count_dict.get, reverse=True)[0]

            if count_dict[top_result] > 0:
                logging.info(f"command '{top_result}' won with {count_dict[top_result]} votes")
                self.__movement_callback(top_result)
