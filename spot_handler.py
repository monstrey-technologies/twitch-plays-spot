import logging
import time

import cv2
import numpy as np
from bosdyn.api import image_pb2
from bosdyn.client import create_standard_sdk, \
    RpcError, \
    lease, \
    estop, \
    robot_command, \
    robot_state, \
    power, \
    image, \
    InvalidRequestError
from bosdyn.client.estop import EstopKeepAlive
from bosdyn.client.lease import LeaseKeepAlive
from bosdyn.client.payload_registration import InvalidPayloadCredentialsError
from bosdyn.client.power import BatteryMissingError
from bosdyn.client.robot_command import NoTimeSyncError, NotPoweredOnError, RobotCommandBuilder


class Spot:
    app_name = "twitch_client"
    __robot = None
    __sdk = None

    __lease_client = None
    __power_client = None
    __estop_client = None
    __state_client = None
    __command_client = None

    __estop_endpoint = None
    __estop_keepalive = None

    __lease = None
    __lease_keep_alive = None
    movement_helper = None
    image_helper = None

    def __init__(self, config):
        logging.info(f"Creating new robot instance for {config.name} {config.host}")
        self.hostname = config.host
        self.client_name = config.name
        self.guid = config.guid
        self.secret = config.secret

    def connect(self, cb=None, retry=False):
        self.__sdk = create_standard_sdk(self.app_name)
        try:
            self.__robot = self.__sdk.create_robot(self.hostname)
            logging.info(f"Authenticating payload with guid {self.guid}")
            self.__robot.authenticate_from_payload_credentials(guid=self.guid, secret=self.secret)
            logging.info("Starting time sync")
            self.__robot.start_time_sync()

            self.__preflight()
            if cb is not None:
                cb()
        except RpcError:
            logging.error(f"Could not connect with robot using {self.hostname}")
            if retry:
                logging.info(f"Retrying using {self.hostname}")
                self.connect(cb, retry)
        except InvalidPayloadCredentialsError:
            logging.error(f"Invalid guid '{self.guid}' or secret")
        except Exception as exc:
            logging.error(exc)

    def __preflight(self):
        logging.info("Ensuring clients")
        self.__lease_client = self.__robot.ensure_client(lease.LeaseClient.default_service_name)
        self.__power_client = self.__robot.ensure_client(power.PowerClient.default_service_name)
        self.__state_client = self.__robot.ensure_client(robot_state.RobotStateClient.default_service_name)
        self.__estop_client = self.__robot.ensure_client(estop.EstopClient.default_service_name)
        self.__command_client = self.__robot.ensure_client(robot_command.RobotCommandClient.default_service_name)
        self.__image_client = self.__robot.ensure_client(image.ImageClient.default_service_name)

        logging.info("Initializing movement helper")
        self.movement_helper = MovementHelper(self.__command_client)
        logging.info("Initializing image helper")
        self.image_helper = ImageViewer(self.__image_client)

    def get_battery_level(self):
        return self.__state_client.get_robot_state().battery_states[0].charge_percentage.value

    def enable_movement(self):
        if self.__lease is None:
            logging.info("Acquiring lease")
            self.__lease = self.__lease_client.take()
            self.__lease_keep_alive = LeaseKeepAlive(self.__lease_client)

        if self.__estop_endpoint is None:
            logging.info("Creating estop endpoint")
            self.__estop_endpoint = estop.EstopEndpoint(client=self.__estop_client, name='mt-node-payload',
                                                        estop_timeout=9)

        self.__estop_endpoint.force_simple_setup()
        self.__estop_keepalive = EstopKeepAlive(self.__estop_endpoint)

        try:
            logging.info("Powering motors")
            power.power_on(self.__power_client)
        except BatteryMissingError:
            logging.error("Batter missing")

    def disable_movement(self):
        logging.info("Depowering motors")
        power.power_off(self.__power_client)

        if self.__lease is not None:
            logging.info("Releasing lease")
            self.__lease_keep_alive.shutdown()
            self.__lease_client.return_lease(self.__lease)
            self.__lease = None

        if self.__estop_endpoint is not None:
            logging.info("Releasing estop")
            self.__estop_keepalive.stop()
            self.__estop_keepalive = None

            self.__estop_endpoint.stop()
            self.__estop_endpoint = None


class ImageViewer:
    __sources = ['frontright_fisheye_image', 'frontleft_fisheye_image']

    def __init__(self, image_client):
        self.__image_client = image_client

    def update_sources(self, sources):
        self.__sources = sources

    def stream_images(self, delay=500):
        logging.info(f"Starting imagestream for {self.__sources} with a refreshrate of {delay}")
        keep_streaming = True
        image_dict = {}

        while keep_streaming:
            image_responses = self.__image_client.get_image_from_sources(
                self.__sources)
            for image_response in image_responses:
                if image_response.shot.image.pixel_format == image_pb2.Image.PIXEL_FORMAT_DEPTH_U16:
                    d_type = np.uint16
                else:
                    d_type = np.uint8

                img = np.frombuffer(image_response.shot.image.data, dtype=d_type)
                if image_response.shot.image.format == image_pb2.Image.FORMAT_RAW:
                    img = img.reshape(image_response.shot.image.rows,
                                      image_response.shot.image.cols)
                else:
                    img = cv2.imdecode(img, -1)
                img = cv2.resize(img, (480, 480), interpolation=cv2.INTER_AREA)
                if image_response.source.name == 'frontright_fisheye_image' or image_response.source.name == 'frontleft_fisheye_image':
                    img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                elif image_response.source.name == 'right_fisheye_image':
                    img = cv2.rotate(img, cv2.ROTATE_180)

                image_dict[image_response.source.name] = img
                cv2.imshow('image', np.concatenate(
                    list(image_dict.values()), axis=1))

            key_pressed = cv2.waitKey(delay)
            if key_pressed == 32:
                keep_streaming = False


class MovementHelper:
    __VELOCITY_BASE_SPEED = 0.5
    __VELOCITY_BASE_ANGULAR = 0.8
    __VELOCITY_CMD_DURATION = 0.6

    def __init__(self, command_client):
        self.command_client = command_client

    def __execute_command(self, description, command, end_time=None):
        try:
            logging.info(f"Sending command {description}")
            self.command_client.robot_command(command, end_time)
        except RpcError:
            logging.error("Problem communicating with the Spot")
        except InvalidRequestError:
            logging.error("Invalid request")
        except NoTimeSyncError:
            logging.error("It's been too long since last time-sync")
        except NotPoweredOnError:
            logging.error("Engines are not powered")

    def __execute_velocity(self, description, v_x=0.0, v_y=0.0, v_rot=0.0):
        self.__execute_command(
            description,
            RobotCommandBuilder.synchro_velocity_command(
                v_x=v_x,
                v_y=v_y,
                v_rot=v_rot
            ),
            time.time() + self.__VELOCITY_CMD_DURATION

        )

    def sit(self):
        self.__execute_command("sit", RobotCommandBuilder.synchro_sit_command())

    def stand(self):
        self.__execute_command("stand", RobotCommandBuilder.synchro_stand_command())

    def forward(self):
        self.__execute_velocity("forward", v_x=self.__VELOCITY_BASE_SPEED)

    def backward(self):
        self.__execute_velocity("backward", v_x=-self.__VELOCITY_BASE_SPEED)

    def left(self):
        self.__execute_velocity("left", v_y=-self.__VELOCITY_BASE_SPEED)

    def right(self):
        self.__execute_velocity("right", v_y=-self.__VELOCITY_BASE_SPEED)

    def rotate_left(self):
        self.__execute_velocity("rotate_left", v_rot=self.__VELOCITY_BASE_ANGULAR)

    def rotate_right(self):
        self.__execute_velocity("rotate_right", v_rot=-self.__VELOCITY_BASE_ANGULAR)
