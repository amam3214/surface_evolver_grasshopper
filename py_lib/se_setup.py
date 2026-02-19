import os
import pathlib

import py_lib


L_CURLY = r"{"
R_CURLY = r"}"

## Optimization ##
def generate_fe_file_string(arguments):
    fe_file_str, volumes_of_mesh, initial_target_length = py_lib.load_mesh.get_mesh_topology_for_fe(arguments["input_mesh"], arguments["input_boundary_conditions"], arguments["boundary_curves"], arguments["approx_curves"])

    fe_file_str += f"read // Take and run SE commands from this file\n"
    fe_file_str += f"G 0; //\n"
    for i, volume in enumerate(volumes_of_mesh):
        fe_file_str += f"set body target {volume * arguments['VOLUME_FACTOR']} where id == {i+1} // Sets the volume\n"
    if arguments['INTER_ACTIVE']:
        fe_file_str += f"s // Open graphics window\nq\n"
        fe_file_str += f'read "{os.path.join(arguments["BASE_PATH"], "surface_evolver_grasshopper", "se_lib", "docstring.ses")}"\n'.replace('\\', '\\\\')


    fe_file_str += f"optimize_step := {{ g; // A general function looking for minimum\n"
    fe_file_str += f"    g {arguments['G_INPUT']};\n"
    fe_file_str += f"    hessian_seek;\n"
    fe_file_str += f"    hessian_seek;\n"
    fe_file_str += f"    o;\n"
    fe_file_str += f"}}\n"
    
    base_path = arguments['BASE_PATH'].replace("\\", "\\\\")
    dmp_path = arguments['TEMP_DMP_PATH'].replace("\\", "\\\\")
    stl_path = arguments['TEMP_STL_PATH'].replace("\\", "\\\\")
    stl_cmd_path = os.path.join(arguments['BASE_PATH'], r"fe\stl.cmd").replace("\\", "\\\\")
    fe_file_str += f"read \"{stl_cmd_path}\"\n"
    fe_file_str += f"dump_file := {{ dump \"{dmp_path}\" }}\n"
    fe_file_str += f"dump_stl  := {{ stl >>> \"{stl_path}\" }}\n"
    fe_file_str += f"target_length := {initial_target_length:.2f};\n"
    fe_file_str += f"loose_remesh_step := {{t target_length/16*9; l target_length/16*25; V 2; u; u;}}\n"
    fe_file_str += f"remesh_step := {{t target_length/4*3; l target_length/4*5; V 2; u; u;}}\n"

    fe_file_str += "dmp_idx := 0;\n"
    fe_file_str += "dump_stl_inc := { \n"
    fe_file_str += "    dmp_idx += 1;\n"
    fe_file_str += "    local fname;\n"
    fe_file_str += "    fname := sprintf \"" + base_path + "\\\\stl_dumps\\\\%d.stl\", dmp_idx;\n"
    fe_file_str += "    stl >>> fname;\n"
    fe_file_str += "    printf \"Wrote %s\\n\", fname;\n"
    fe_file_str += "}\n"

    fe_file_str += "loose_and_remesh := {\n"
    fe_file_str += "    target_length := target_length * 1.3;\n"
    fe_file_str += "    loose_remesh_step;\n"
    fe_file_str += "    loose_remesh_step;\n"
    fe_file_str += "}\n"

    # Script
    fe_file_str += "dump_stl_inc\n"
    for i in range (4):
        fe_file_str += f"loose_and_remesh;\n"
        fe_file_str += "dump_stl_inc\n"
    fe_file_str += "V 10; u;\n"
    fe_file_str += "dump_stl_inc\n"
    for i in range (10):
        fe_file_str += f";g\n"
        fe_file_str += "dump_stl_inc\n"
    for i in range (4):
        fe_file_str += f"hessian_seek;\n"
        fe_file_str += "dump_stl_inc\n"
    fe_file_str += "dump_stl;\n"

    #####################
    # fe_file_str += "dump_file;\n"
    # fe_file_str += "loose_remesh_step; loose_remesh_step;\n"
    # fe_file_str += "optimize_step;\n"
    # fe_file_str += "loose_remesh_step; loose_remesh_step;\n"
    # fe_file_str += "target_length := target_length / 2;\n"
    # fe_file_str += "loose_remesh_step; loose_remesh_step;\n"
    # fe_file_str += f"remesh_step; optimize_step; remesh_step; optimize_step; // Attempt better remeshing\n"
    # fe_file_str += f"optimize_step; loose_remesh_step; optimize_step; hessian_seek // finall settling down - stay true to the physics. \n"
    # fe_file_str += f"s; \n"

    if not arguments['INTER_ACTIVE']:
        # fe_file_str += 'dump_file; r 2; g 100; hessian; dump_stl; q; q;\n'
        # fe_file_str += 'dump_file; r; g 40; u; V 50; r; u; V 50; g 50; hessian; hessian; hessian; dump_stl; q; q;\n'
        fe_file_str += "dump_file;\n"
        fe_file_str += "loose_remesh_step; loose_remesh_step;\n"
        fe_file_str += "optimize_step;\n"
        fe_file_str += "loose_remesh_step; loose_remesh_step;\n"
        fe_file_str += "target_length := target_length / 2;\n"
        fe_file_str += "loose_remesh_step; loose_remesh_step;\n"
        fe_file_str += f"remesh_step; optimize_step; remesh_step; optimize_step; // Attempt better remeshing\n"
        fe_file_str += f"optimize_step; loose_remesh_step; optimize_step; hessian_seek // final settling down - stay true to the physics. \n"
        fe_file_str += f"s; \n"

        # fe_file_str += 'U;'
        # for r in range(arguments['R_INPUT']):
        #     fe_file_str += 'g;r;'
        # #     if r != 0:
        # #         fe_file_str += "loose_remesh_step; loose_remesh_step;\n"
        # #         fe_file_str += "target_length := target_length / 2;\n"
        # #         fe_file_str += "loose_remesh_step; loose_remesh_step;\n"
        # #     else:
        # #         fe_file_str += "loose_remesh_step; loose_remesh_step;\n"
        # #     fe_file_str += "optimize_step;\n"
        # #
        # # fe_file_str += f"remesh_step; optimize_step; remesh_step; optimize_step; // Attempt better remeshing\n"
        # # fe_file_str += f"optimize_step; loose_remesh_step; optimize_step; // finall settling down - stay true to the physics. \n"
        # fe_file_str += 'g 150;'
        # # fe_file_str += "dump_file\n"
        # fe_file_str += f"stl >>> \"{stl_path}\"\n"
        # fe_file_str += "q\n"
        # fe_file_str += "q\n"
    # else:
    #     fe_file_str += 'printf "\\n\\n\\n\\n\\n\\n\\n\\n"; print_help;'
    
    return fe_file_str

def clean_temps(arguments):
    if os.path.isfile(arguments['TEMP_FE_PATH']):
        pathlib.Path.unlink(arguments['TEMP_FE_PATH'])
    if os.path.isfile(arguments['TEMP_DMP_PATH']):
        pathlib.Path.unlink(arguments['TEMP_DMP_PATH'])
