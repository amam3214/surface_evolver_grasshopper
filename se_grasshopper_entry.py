import os
import sys
import subprocess
import Rhino
import platform

TOLERANCE = 1e-5


def import_or_reload(name):
    if name in sys.modules:
        import importlib
        importlib.invalidate_caches()
        return importlib.reload(sys.modules[name])
    return __import__(name)
py_lib = import_or_reload("py_lib")

## Execution ##
def main(args):
    assert_input(args, do_assert=True)
    args["approx_curves"] = match_boundaries(args)

    args['TEMP_FE_PATH'] = os.path.join(args['BASE_PATH'], r"temp_fe_file_for_grasshopper_script.fe")
    args['TEMP_DMP_PATH'] = os.path.join(args['BASE_PATH'], r"temp_fe_file_for_grasshopper_script.dmp")
    args['TEMP_STL_PATH'] = os.path.join(args['BASE_PATH'], r"temp.stl")
    args['SE_PATH'] = os.path.join(args['BASE_PATH'], r"evolver.exe")
    if not os.path.isfile(args['SE_PATH']):
        args['SE_PATH'] = os.path.join(args['BASE_PATH'], r"evolver")
        if not os.path.isfile(args['SE_PATH']):
            print("evolver executable not exists in the required path\n\n")
            return
        
    fe_file_string = py_lib.se_setup.generate_fe_file_string(args)
    with open(f"{args['TEMP_FE_PATH']}", "w") as temp_fe:
        temp_fe.write(fe_file_string)

    system = platform.system()
    if system == "Windows":
        subprocess.run([f"{args['SE_PATH']}", f"{args['TEMP_FE_PATH']}"])
    elif system == "Darwin":
        mac_cmd = f"'{args['SE_PATH']}' '{args['TEMP_FE_PATH']}'"
        apple_script = f'''
        tell application "Terminal"
            activate
            do script "{mac_cmd}"
        end tell
        '''
        subprocess.run(["osascript", "-e", apple_script])

    # if not os.path.isfile(args['TEMP_STL_PATH']):
    #     print("Surface Evolver Failed")
    #     return

    # with open(f"{args['TEMP_DMP_PATH']}", "r") as temp_dmp:
    #     results_text = temp_dmp.read()
    #
    # py_lib.reconstruct_mesh.reconstruct_mesh(args, results_text)
    out_mesh = py_lib.reconstruct_mesh.parse_se_stl(args['TEMP_STL_PATH'])
    return out_mesh

def match_boundaries(args):
    ideal_curves  = args["boundary_curves"]
    approx_curves = args["approx_curves"]
    assert len(ideal_curves) == len(approx_curves), f"Got different number of ideal ({len(ideal_curves)}) and approximate ({len(approx_curves)}) boundary curves"

    new_approx_curves = []
    for ideal in ideal_curves:
        length = ideal.GetLength()
        for approx in approx_curves:
            success, p0, p1 = ideal.ClosestPoints(approx)
            assert success
            if ((p0 - p1).Length < TOLERANCE * length):
                new_approx_curves.append(approx)
                break

    assert len(ideal_curves) == len(new_approx_curves), f"Could not match all approximate and ideal curves: {len(new_approx_curves)}/{len(ideal_curves)} matched"

    return new_approx_curves

def assert_input(args, do_assert=True):
    input_mesh = args["input_mesh"]
    input_boundary_conditions = args["input_boundary_conditions"]
    boundary_curves = args["boundary_curves"]
    if do_assert: assert(hasattr(input_mesh, '__iter__'))
    if do_assert: assert(hasattr(input_boundary_conditions, '__iter__'))
    if do_assert: assert(hasattr(boundary_curves, '__iter__'))
    
    for i, mesh in enumerate(input_mesh):
        if do_assert: assert(type(mesh) == Rhino.Geometry.Mesh)
        mesh.Vertices.CombineIdentical(True, True)
        mesh.Vertices.CullUnused()
        mesh.Faces.CullDegenerateFaces()
        mesh.FaceNormals.ComputeFaceNormals()
        if do_assert: assert mesh.IsManifold(), f"Mesh {i} is not a manifold."
        if do_assert: assert mesh.IsOriented, f"Mesh {i} is not oriented."
        if do_assert: assert mesh.IsClosed, f"Mesh {i} is not closed."
