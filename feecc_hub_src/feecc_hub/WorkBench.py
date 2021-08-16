from __future__ import annotations

import threading
import typing as tp
from random import randint

from loguru import logger

from ._State import State, AwaitLogin
from .Employee import Employee
from .Types import ConfigSection
from .Unit import Unit
from ._Camera import Camera
from ._external_io_operations import ExternalIoGateway

if tp.TYPE_CHECKING:
    from .Types import Config
    from .Hub import Hub


class WorkBench:
    """
    Work bench is a union of an Employee, working at it,
    Camera attached to it and associated Agent.
    It provides highly abstract interface for interaction with them
    """

    def __init__(self, associated_hub: Hub, workbench_config: tp.Dict[str, tp.Any]) -> None:
        self._workbench_config: tp.Dict[str, tp.Any] = workbench_config
        self.number: int = self._workbench_config["workbench number"]
        self.associated_hub: Hub = associated_hub
        self._associated_camera: tp.Optional[Camera] = self._get_camera()
        self.employee: tp.Optional[Employee] = None
        self.associated_unit: tp.Optional[Unit] = None
        self.io_gateway: ExternalIoGateway = ExternalIoGateway(self.config)
        logger.info(f"Workbench no. {self.number} initialized")
        logger.debug(f"Raw workbench configuration:\n{self._workbench_config}")
        self.state: tp.Optional[State] = None
        self.previous_state: tp.Optional[tp.Type[State]] = None
        self._state_thread_list: tp.List[threading.Thread] = []
        self.execute_state(AwaitLogin)

    @property
    def _state_thread(self) -> tp.Optional[threading.Thread]:
        return self._state_thread_list[-1] if self._state_thread_list else None

    @_state_thread.setter
    def _state_thread(self, state_thread: threading.Thread) -> None:
        self._state_thread_list.append(state_thread)
        thread_list = self._state_thread_list
        logger.debug(
            f"Attribute _state_thread_list of Agent is now of len {len(thread_list)}:\n"
            f"{[repr(t) for t in thread_list]}\n"
            f"Threads alive: {list(filter(lambda t: t.is_alive(), thread_list))}"
        )

    @property
    def config(self) -> Config:
        return self.associated_hub.config

    @property
    def camera(self) -> tp.Optional[Camera]:
        return self._associated_camera

    @property
    def unit_in_operation(self) -> tp.Optional[str]:
        return str(self.associated_unit.internal_id) if self.associated_unit else None

    @property
    def is_operation_ongoing(self) -> bool:
        return bool(self.unit_in_operation)

    @property
    def state_name(self) -> tp.Optional[str]:
        return self.state.name if self.state else None

    @property
    def state_description(self) -> tp.Optional[str]:
        return str(self.state.description) if self.state else None

    def _get_camera(self) -> tp.Optional[Camera]:
        camera_config: tp.Optional[ConfigSection] = self._workbench_config["hardware"]["camera"]
        return Camera(camera_config) if camera_config else None

    def execute_state(self, state: tp.Type[State], *args: tp.Any, **kwargs: tp.Any) -> None:
        """execute provided state in the background"""
        self.previous_state = self.state.__class__ if self.state else None
        self.state = state(self)
        if self.state is None:
            raise ValueError("Current state undefined")

        logger.info(f"Agent state is now {self.state.name}")

        # execute state in the background
        logger.debug(f"Trying to execute state: {state}")
        thread_name: str = f"{self.state.name}-{randint(1, 999)}"
        self._state_thread = threading.Thread(
            target=self.state.perform_on_apply,
            args=args,
            kwargs=kwargs,
            daemon=False,
            name=thread_name,
        )
        self._state_thread.start()
