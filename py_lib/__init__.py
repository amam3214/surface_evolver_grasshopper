import sys
import importlib
def import_or_reload(name, *args):
    if name in sys.modules:
        return importlib.reload(sys.modules[name])
    return __import__(name)

load_mesh = import_or_reload("load_mesh")
reconstruct_mesh = import_or_reload("reconstruct_mesh")
se_setup = import_or_reload("se_setup")
