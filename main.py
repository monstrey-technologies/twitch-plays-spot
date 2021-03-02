import logging
import coloredlogs
import threading
from dataclasses import dataclass

import yaml

from bot import TwitchBot
from message_server import Server
from spot_handler import Spot

from constants import MOVEMENT_BACKWARD, MOVEMENT_FORWARD, MOVEMENT_SIT, MOVEMENT_STAND, MOVEMENT_STRAFE_LEFT, \
    MOVEMENT_STRAFE_RIGHT, MOVEMENT_TURN_LEFT, MOVEMENT_TURN_RIGHT


@dataclass
class Configuration:
    host: str
    name: str
    guid: str
    secret: str
    twitch_token: str


class TwitchPlays:
    __spot = None
    __bot = None
    __config = None
    __last_move = None
    __allow_movement = True

    def __init__(self):
        self.load_logging_configuration("INFO")
        self.__config = self.read_yaml()
        pass

    def activate_server(self):
        threading.Thread(
            target=Server(movement_callback=self.cb_movement, stat_callback=self.cb_stats).start).start()

    def activate_bot(self):
        if self.__config is not None:
            self.__bot = TwitchBot("monstreytechnologies", None, self.__config.twitch_token, "monstreytechnologies",
                                   self.cb_movement)
            threading.Thread(target=self.__bot.start).start()
        else:
            logging.error("Invalid configuration")

    def activate_spot(self):
        if self.__config is not None:
            self.__spot = Spot(self.__config)

            def cb():
                threading.Thread(target=self.__spot.image_helper.stream_images).start()
                self.__spot.enable_movement()

            threading.Thread(target=self.__spot.connect, args=[cb, True]).start()
        else:
            logging.error("Invalid configuration")

    def cb_movement(self, move):
        if self.__spot is not None:
            if move == "pause":
                self.__allow_movement = False
            elif move == "resume":
                self.__allow_movement = True
            elif self.__allow_movement:
                self.__last_move = move
                return {
                    MOVEMENT_SIT: self.__spot.movement_helper.sit,
                    MOVEMENT_STAND: self.__spot.movement_helper.stand,
                    MOVEMENT_FORWARD: self.__spot.movement_helper.forward,
                    MOVEMENT_BACKWARD: self.__spot.movement_helper.backward,
                    MOVEMENT_TURN_LEFT: self.__spot.movement_helper.rotate_left,
                    MOVEMENT_TURN_RIGHT: self.__spot.movement_helper.rotate_right,
                    MOVEMENT_STRAFE_LEFT: self.__spot.movement_helper.left,
                    MOVEMENT_STRAFE_RIGHT: self.__spot.movement_helper.right
                }.get(move, lambda: logging.error(f"Invalid move command: {move}"))()

        else:
            logging.error(f"Could not trigger {move} since Spot has not been initialised")

    def cb_stats(self, stat):
        if stat == "battery" and self.__spot is not None:
            return {"stat": self.__spot.get_battery_level()}
        elif stat == "viewcount":
            return {"stat": self.__bot.get_chat_count()}
        elif stat == "lastcommand":
            return {"stat": self.__last_move}

    @staticmethod
    def load_logging_configuration(level):
        coloredlogs.install(level=level, fmt='%(asctime)s.%(msecs)03d %(levelname)-8s %(filename)-20s %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')

    @staticmethod
    def read_yaml():
        with open("config.yaml", 'r') as stream:
            try:
                yaml_config = yaml.unsafe_load(stream)

                return Configuration(
                    host=yaml_config["connection"]["host"],
                    name=yaml_config["connection"]["name"],
                    guid=yaml_config["payload"]["guid"],
                    secret=yaml_config["payload"]["secret"],
                    twitch_token=yaml_config["twitch"]["token"]
                )
            except yaml.YAMLError as err:
                logging.error(err)
                return None


def main():
    twitch_plays = TwitchPlays()

    twitch_plays.activate_bot()
    twitch_plays.activate_server()
    twitch_plays.activate_spot()


if __name__ == '__main__':
    main()
