import re
import os
import Rhino


SCALE_FACTOR = 1
VERTCIES_START = "vertices        /*  coordinates  */    \n"
EDGES_START = "edges  "
FACETS_START = "faces    /* edge loop */      "


def get_line_items(line):
    while "  " in line:
        line = line.replace("  ", " ")
    if line[0] == " ":
        line = line[1:]
    items = line.split(" ")
    returned_items = []
    for item in items:
        if item.isdigit() or (item and item[0] == "-" and item[1:].isdigit()):
            returned_items.append(int(item))
        elif re.findall(r"^-?\d+(\.\d+)?(e(-|\+)\d+)?$", item):
            returned_items.append(float(item))
        else:
            returned_items.append(item)
    return returned_items

def create_mesh(file_string):
    file_string = file_string.replace("\r\n", "\n").replace("\r", "\n")
    start_index = file_string.find(VERTCIES_START) + len(VERTCIES_START)
    if start_index == len(VERTCIES_START) - 1:
        print("Can't find vertcies start in .dmp file, must be a bug in the script or SE version was changed.")
        return
    
    file_string = file_string[start_index:]
    verts = []
    verts_id_to_index = {}
    edges_to_verts = {}
    fixed_faces = []
    full_faces = []
    mod = "add verts"
    for line in file_string.split("\n"):
        if mod == "add verts":
            if line == EDGES_START:
                mod = "track edges"
            elif len(line) > 3:
                id, x, y, z = get_line_items(line)[:4]
                verts_id_to_index[id] = len(verts)
                verts.append((x * SCALE_FACTOR, y * SCALE_FACTOR, z * SCALE_FACTOR))
        
        elif mod == "track edges":
            if line == FACETS_START:
                mod = "add faces"
            elif len(line) > 3:
                edge, vert1, vert2 = get_line_items(line)[:3]
                edges_to_verts[   edge] = (vert1, vert2)
                edges_to_verts[ - edge] = (vert2, vert1)
        
        elif mod == "add faces":
            if len(line) < 3:
                break
            elif len(line) > 3:
                items = get_line_items(line)
                edge1, edge2, edge3 = items[1:4]
                assert edges_to_verts[edge1][1] == edges_to_verts[edge2][0]
                assert edges_to_verts[edge2][1] == edges_to_verts[edge3][0]
                assert edges_to_verts[edge3][1] == edges_to_verts[edge1][0]
                full_faces.append((verts_id_to_index[edges_to_verts[edge1][0]],
                                    verts_id_to_index[edges_to_verts[edge2][0]],
                                    verts_id_to_index[edges_to_verts[edge3][0]]))
                    
                if "fixed" in items:
                    fixed_faces.append((verts_id_to_index[edges_to_verts[edge1][0]],
                                       verts_id_to_index[edges_to_verts[edge2][0]],
                                       verts_id_to_index[edges_to_verts[edge3][0]]))
                
    return (verts, full_faces, fixed_faces)


def reconstruct_mesh(arguments, results_text):
    verts, faces, fixed_faces = create_mesh(results_text)
    arguments['result_mesh']['verts'], arguments['result_mesh']['faces'] = verts, faces
    arguments['result_fixed']['verts'], arguments['result_fixed']['faces'] = verts, fixed_faces

def parse_se_stl(file_path):
    """
    Parses an ASCII STL from Surface Evolver and returns a welded Rhino Mesh.
    """
    if not file_path or not os.path.exists(file_path):
        return "Surface Evolver STL file not found"

    temp_mesh = Rhino.Geometry.Mesh()
    
    # Read the file line-by-line
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
    except IOError as e:
        return "Error reading STL file: " + str(e)

    # STL format: 3 "vertex" lines followed by "endloop"
    for line in lines:
        if "vertex" in line:
            # Line format: "      vertex 1.234 5.678 9.012"
            parts = line.split()
            # parts[0] is 'vertex', parts[1..3] are coords
            x = float(parts[1])
            y = float(parts[2])
            z = float(parts[3])
            
            temp_mesh.Vertices.Add(x, y, z)
            
        elif "endloop" in line:
            # We just added 3 vertices. Create a face from them.
            # The indices are the last 3 added.
            cnt = temp_mesh.Vertices.Count
            temp_mesh.Faces.AddFace(cnt - 3, cnt - 2, cnt - 1)

    # STL is "triangle soup" (every face has its own unique 3 vertices).
    # Therefore we weld adjacent veritces.
    
    # True, True = Ignore normals when merging, Delete unused vertices
    temp_mesh.Vertices.CombineIdentical(True, True)
    
    # Cleanup
    temp_mesh.Normals.ComputeNormals()
    temp_mesh.Compact()
    
    return temp_mesh
