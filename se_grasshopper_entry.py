import os
import sys
import subprocess
import Rhino

def import_or_reload(name):
    if name in sys.modules:
        import importlib
        importlib.invalidate_caches()
        return importlib.reload(sys.modules[name])
    return __import__(name)
py_lib = import_or_reload("py_lib")

## Execution ##
def main(args):
    assert_input(args)

    args['TEMP_FE_PATH'] = os.path.join(args['BASE_PATH'], r"temp_fe_file_for_grasshopper_script.fe")
    args['TEMP_DMP_PATH'] = os.path.join(args['BASE_PATH'], r"temp_fe_file_for_grasshopper_script.dmp")
    args['SE_PATH'] = os.path.join(args['BASE_PATH'], r"evolver.exe")
    if not os.path.isfile(args['SE_PATH']):
        args['SE_PATH'] = os.path.join(args['BASE_PATH'], r"evolver")
        if not os.path.isfile(args['SE_PATH']):
            print("evolver executable not exists in the required path\n\n")
            return 
        
    fe_file_string = py_lib.se_setup.generate_fe_file_string(args)
    with open(f"{args['TEMP_FE_PATH']}", "w") as temp_fe:
        temp_fe.write(fe_file_string)

    subprocess.run([f"{args['SE_PATH']}", f"{args['TEMP_FE_PATH']}"])

    if not os.path.isfile(args['TEMP_DMP_PATH']):
        print("Surface Evolver Failed")
        #clean_temps()
        return

    with open(f"{args['TEMP_DMP_PATH']}", "r") as temp_dmp:
        results_text = temp_dmp.read()
    
    py_lib.reconstruct_mesh.reconstruct_mesh(args, results_text)
    return 

def assert_input(args):
    input_mesh = args["input_mesh"]
    input_boundary_conditions = args["input_boundary_conditions"]
    assert(hasattr(input_mesh, '__iter__'))
    assert(hasattr(input_boundary_conditions, '__iter__'))
    
    for i, mesh in enumerate(input_mesh):
        assert(type(mesh) == Rhino.Geometry.Mesh)
        mesh.Vertices.CombineIdentical(True, True)
        mesh.Vertices.CullUnused()
        mesh.Faces.CullDegenerateFaces()
        mesh.FaceNormals.ComputeFaceNormals()
        assert mesh.IsManifold(), f"Mesh {i} is not a manifold."
        assert mesh.IsOriented, f"Mesh {i} is not oriented."
        assert mesh.IsClosed, f"Mesh {i} is not closed."
