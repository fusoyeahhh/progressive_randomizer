import sys
import types
import inspect
import pkgutil
import importlib

import logging
log = logging.getLogger()

import contextlib

from ...components import MemoryStructure
from ...randomizers import FF6StaticRandomizer

from .....tasks import WriteBytes

from wc import memory as wc_memory
from wc.memory.space import Space
from wc.memory.rom import ROM
from wc.memory.free import free

class LoggedROMWriter(ROM, contextlib.AbstractContextManager):
    def __init__(self, bindata):
        self._tasks = []
        self.data = list(bindata[:])

    def __enter__(self):
        # Have to reset all the module level variables
        # FIXME: may want to serialize this somehow
        Space.heaps = {bank: wc_memory.space.Heap()
                       for bank in wc_memory.space.Bank}
        Space.spaces = []
        Space.rom = self

        # FIXME: find a way to clear this for each invocation
        # This calls some module level global initialization stuff
        free()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    # file_name is unused, just there to allow this function to be called
    # in the same way as the parent class
    def write(self, file_name=None):
        pass

    def set_bits(self, address, mask, value, **kwargs):
        self._tasks.append(
            WriteBytes(
                MemoryStructure(
                    addr=address, length=1,
                    name=kwargs.get("name", "wc write"),
                    descr=kwargs.get("descr", "dummy memblk")
                ),
                self.data[address]
            )
        )
        return super().set_bits(address, mask, value)

    def set_bit_num(self, address, bit_num, value, **kwargs):
        self._tasks.append(
            WriteBytes(
                MemoryStructure(
                    addr=address, length=1,
                    name=kwargs.get("name", "wc write"),
                    descr=kwargs.get("descr", "dummy memblk")
                ),
                self.data[address]
            )
        )
        return super().set_bit_num(address, bit_num, value)

    def set_byte(self, address, value, **kwargs):
        self._tasks.append(
            WriteBytes(
                MemoryStructure(
                    addr=address, length=1,
                    name=kwargs.get("name", "wc write"),
                    descr=kwargs.get("descr", "dummy memblk")
                ),
                value
            )
        )
        return super().set_byte(address, value, **kwargs)

    def set_bytes(self, address, values, **kwargs):
        self._tasks.append(
            WriteBytes(
                MemoryStructure(
                    addr=address, length=len(values),
                    name=kwargs.get("name", "wc write"),
                    descr=kwargs.get("descr", "dummy memblk")
                ),
                values
            )
        )
        return super().set_bytes(address, values, **kwargs)

class _WorldsCollide:
    @classmethod
    def get_watcher(cls, bindata):
        return LoggedROMWriter(bindata)

    def apply_wc_patch(self, *patches):
        tasks = []
        with self.logger as ctx:
            for patch in patches:
                patch(self)
                tasks.extend(self.logger._tasks)
                self.logger._tasks = []

        return tasks

    def _install(self, name, func):
        def _wrap_wc_patch(self):
            return self.apply_wc_patch(func)
        log.debug(f"_WorldsCollide: installing {name} -> {func}")
        setattr(self, name, types.MethodType(_wrap_wc_patch, self))

    def _install_from_cls(self, name, func):
        log.info(f"_WorldsCollide: installing {name} -> {func}")
        setattr(self, name, types.MethodType(func, self))

    def _install_cls(self, cname, cls, entry="mod", exclude_dunder=True):
        for name, func in inspect.getmembers(cls, inspect.isfunction):
            if exclude_dunder and name.startswith("_"):
                continue

            args = inspect.getfullargspec(func).args
            if len(args) == 1 and args == ["self"]:
                if name == entry:
                    name = cname.lower()
                else:
                    name = f"{cname}_{name}"
                self._install(name, func)

    def install_wc(self):
        # FIXME: wc does on the fly reads...
        self.logger = self.get_watcher(b"\x00" * (4 * 1024**2))

        # This has to be done in the logger context, since there's a complicated
        # initialization routine that happens within the import chain
        with self.logger as ctx:
            # Handle bug_fix module
            from wc import bug_fixes
            for name, cls in inspect.getmembers(bug_fixes, inspect.isclass):
                self._install_cls(name, cls)

            # Handle event module
            from wc import event
            for cls_mod in pkgutil.iter_modules(event.__path__):
                cls_mod = importlib.import_module(f"wc.event.{cls_mod.name}")
                for name, cls in inspect.getmembers(cls_mod, inspect.isclass):
                    self._install_cls(name, cls)

            # Handle menu module
            from wc import menus
            for cls_mod in pkgutil.iter_modules(menus.__path__):
                cls_mod = importlib.import_module(f"wc.menus.{cls_mod.name}")
                for name, cls in inspect.getmembers(cls_mod, inspect.isclass):
                    self._install_cls(name, cls)

            # Handle battle module
            # FIXME: Can't do this because it depends on undefined args
            """
            from wc import battle
            for cls_mod in pkgutil.iter_modules(battle.__path__):
                cls_mod = importlib.import_module(f"wc.menus.{cls_mod.name}")
                for name, cls in inspect.getmembers(cls_mod, inspect.isclass):
                    self._install_cls(name, cls)
            """

class WorldsCollideRandomizer(FF6StaticRandomizer, _WorldsCollide):
    def __init__(self, seed, flags):
        super().__init__()
        self.install_wc()

        self._seed = seed
        self._flags = flags

    def apply_bug_fixes(self):
        return