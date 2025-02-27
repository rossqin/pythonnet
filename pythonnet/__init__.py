import sys
from os import environ
from pathlib import Path
from typing import Dict, Optional, Union
import clr_loader

__all__ = ["set_runtime", "set_default_runtime", "load"]

_RUNTIME: Optional[clr_loader.Runtime] = None
_LOADER_ASSEMBLY: Optional[clr_loader.wrappers.Assembly] = None
_LOADED: bool = False


def set_runtime(runtime: Union[clr_loader.Runtime, str], **params: str) -> None:
    """Set up a clr_loader runtime without loading it

    :param runtime: Either an already initialised `clr_loader` runtime, or one
    of netfx, coreclr, mono, or default. If a string parameter is given, the
    runtime will be created."""

    global _RUNTIME
    if _LOADED:
        raise RuntimeError(f"The runtime {_RUNTIME} has already been loaded")

    if isinstance(runtime, str):
        runtime = _create_runtime_from_spec(runtime, params)

    _RUNTIME = runtime


def _get_params_from_env(prefix: str) -> Dict[str, str]:

    full_prefix = f"PYTHONNET_{prefix.upper()}_"
    len_ = len(full_prefix)

    env_vars = {
        (k[len_:].lower()): v
        for k, v in environ.items()
        if k.upper().startswith(full_prefix)
    }

    return env_vars


def _create_runtime_from_spec(
    spec: str, params: Optional[Dict[str, str]] = None
) -> clr_loader.Runtime:
    if spec == "default":
        if sys.platform == "win32":
            spec = "netfx"
        else:
            spec = environ.get("PYTHONNET_RUNTIME", "mono")

    params = params or _get_params_from_env(spec)

    if spec == "netfx":
        return clr_loader.get_netfx(**params)
    elif spec == "mono":
        return clr_loader.get_mono(**params)
    elif spec == "coreclr":
        return clr_loader.get_coreclr(**params)
    else:
        raise RuntimeError(f"Invalid runtime name: '{spec}'")


def set_default_runtime() -> None:
    """Set up the default runtime

    This will use the environment variable PYTHONNET_RUNTIME to decide the
    runtime to use, which may be one of netfx, coreclr or mono. The parameters
    of the respective clr_loader.get_<runtime> functions can also be given as
    environment variables, named `PYTHONNET_<RUNTIME>_<PARAM_NAME>`. In
    particular, to use `PYTHONNET_RUNTIME=coreclr`, the variable
    `PYTHONNET_CORECLR_RUNTIME_CONFIG` has to be set to a valid
    `.runtimeconfig.json`.

    If no environment variable is specified, a globally installed Mono is used
    for all environments but Windows, on Windows the legacy .NET Framework is
    used.
    """

    print("Set default RUNTIME")
    raise RuntimeError("Shouldn't be called here")

    spec = environ.get("PYTHONNET_RUNTIME", "default")
    runtime = _create_runtime_from_spec(spec)
    set_runtime(runtime)


def load(
    runtime: Union[clr_loader.Runtime, str] = "default", **params: Dict[str, str]
) -> None:
    """Load Python.NET in the specified runtime

    The same parameters as for `set_runtime` can be used. By default,
    `set_default_runtime` is called if no environment has been set yet and no
    parameters are passed."""
    global _LOADED, _LOADER_ASSEMBLY

    if _LOADED:
        return

    if _RUNTIME is None:
        set_runtime(runtime, **params)

    if _RUNTIME is None:
        raise RuntimeError("No valid runtime selected")

    dll_path = Path(__file__).parent / "runtime" / "Python.Runtime.dll"

    _LOADER_ASSEMBLY = _RUNTIME.get_assembly(str(dll_path))

    func = _LOADER_ASSEMBLY["Python.Runtime.Loader.Initialize"]
    if func(b"") != 0:
        raise RuntimeError("Failed to initialize Python.Runtime.dll")

    import atexit

    atexit.register(unload)


def unload() -> None:
    """Explicitly unload a laoded runtime and shut down Python.NET"""

    global _RUNTIME, _LOADER_ASSEMBLY
    if _LOADER_ASSEMBLY is not None:
        func = _LOADER_ASSEMBLY["Python.Runtime.Loader.Shutdown"]
        if func(b"full_shutdown") != 0:
            raise RuntimeError("Failed to call Python.NET shutdown")

        _LOADER_ASSEMBLY = None

    if _RUNTIME is not None:
        # TODO: Add explicit `close` to clr_loader
        _RUNTIME = None
