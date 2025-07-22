import Rhino


def get_tuple_of_the_edges_of_a_face(face_number, verts, edges):
    edges_of_face = [idx+1 for idx in edges.GetEdgesForFace(face_number)]
    verts_of_edges = [tuple(edges.GetTopologyVertices(idx-1)) for idx in edges_of_face]
    verts_of_face = list(verts.IndicesFromFace(face_number))
    vert_pairs_for_face = list(zip(verts_of_face, verts_of_face[1:] + verts_of_face[:1]))
    for j, pair in enumerate(verts_of_edges):
        if pair not in vert_pairs_for_face:
            edges_of_face[j] *= -1
    return tuple(edges_of_face)

def extract_se_data_from_mesh(meshes, fixed_meshes):
    # bodies
    number_of_bodies = len(list(meshes))
    number_of_faces_of_each_body = [0] * number_of_bodies
    accumulating_number_of_faces = [0] * (number_of_bodies+1)
    volumes_of_mesh              = [0] * number_of_bodies
    mesh = Rhino.Geometry.Mesh()
    for i, this_mesh in enumerate(meshes):
        mesh.Append(this_mesh)
        number_of_faces_of_each_body[i] = this_mesh.Faces.Count
        accumulating_number_of_faces[i+1] = mesh.Faces.Count
        volumes_of_mesh[i] = this_mesh.Volume()

    verts = mesh.TopologyVertices
    edges = mesh.TopologyEdges
    faces = mesh.Faces

    faces_of_each_body_flat = [0] * faces.Count
    interface_pairs = mesh.Faces.GetClashingFacePairs(0)
    for pair in interface_pairs:
        faces_of_each_body_flat[max(pair)] = - (min(pair)+1)
    se_bodies = [0] * number_of_bodies

    number_of_edges = edges.Count
    number_of_verts = verts.Count
    number_of_faces = sum([i==0 for i in faces_of_each_body_flat])

    se_verts = verts
    se_edges = [tuple(edges.GetTopologyVertices(i)) for i in range(number_of_edges)]
    se_faces = [()] * number_of_faces
    face_count = 1
    for i, face in enumerate(faces):
        if (faces_of_each_body_flat[i] < 0): continue
        faces_of_each_body_flat[i] = face_count

        edges_of_face = get_tuple_of_the_edges_of_a_face(i, verts, edges)
        se_faces[face_count-1] = edges_of_face

        face_count += 1

    for i in range(number_of_bodies):
        lo, hi = accumulating_number_of_faces[i:i+2]
        se_bodies[i] = tuple(faces_of_each_body_flat[lo:hi])

    # mark fixed
    fixed_faces = [False] * number_of_faces
    fixed_edges = [False] * number_of_edges
    fixed_verts = [False] * number_of_verts

    for fixed in fixed_meshes:
        combined_mesh = Rhino.Geometry.Mesh()
        combined_mesh.Append(mesh)
        combined_mesh.Append(fixed)
        face_pairs = combined_mesh.Faces.GetClashingFacePairs(0)
        for p in face_pairs:
            if max(p) < faces.Count: continue
            global_face_index = min(p)
            fixed_face_index = abs(faces_of_each_body_flat[global_face_index]) - 1
            if faces_of_each_body_flat[global_face_index] < 0: continue
            fixed_faces[fixed_face_index] = True
            for i in edges.GetEdgesForFace(global_face_index):
                fixed_edges[i] = True
            for i in verts.IndicesFromFace(global_face_index):
                fixed_verts[i] = True

    average_edge_length = sum([edges.EdgeLine(i).Length for i in range(number_of_edges)]) / number_of_edges
    mesh_bbox = mesh.GetBoundingBox(False)
    return se_verts, se_edges, se_faces, se_bodies, fixed_verts, fixed_edges, fixed_faces, volumes_of_mesh, average_edge_length, mesh_bbox

def get_mesh_topology_for_fe(meshes, fixed_meshes):
    se_verts, se_edges, se_faces, se_bodies, fixed_verts, fixed_edges, fixed_faces, volumes_of_mesh, average_edge_length, mesh_bbox = extract_se_data_from_mesh(meshes, fixed_meshes)
    min_X, min_Y, min_Z = mesh_bbox.Min
    max_X, max_Y, max_Z = mesh_bbox.Max

    gemotry_text = ""
    # Write vertices
    gemotry_text += 'vertices\n'
    for i, v in enumerate(se_verts):
        gemotry_text += f"{i+1} {v.X + -(max_X - min_X) * 1.1:.2f} {v.Y:.2f} {v.Z:.2f}"
        if fixed_verts[i]:
            gemotry_text += ' fixed'
        gemotry_text += '\n'
    gemotry_text += '\n'
        
    # Write edges
    gemotry_text += 'edges\n'
    for i, edge in enumerate(se_edges):
        gemotry_text += f"{i+1} {edge[0]+1} {edge[1]+1}"
        if fixed_edges[i]:
            gemotry_text += ' fixed'
        gemotry_text += '\n'
    gemotry_text += '\n'

    # Write faces
    gemotry_text += 'faces\n'
    face_index = 1
    for i, face in enumerate(se_faces):
        gemotry_text += f'{i+1}'
        for edge_of_face in face:
            gemotry_text += f' {edge_of_face}'
        if fixed_faces[i]:
            gemotry_text += ' fixed'
        gemotry_text += '\n'
    gemotry_text += '\n'

    # Write bodies
    gemotry_text += 'bodies\n'
    for i, body in enumerate(se_bodies):
        gemotry_text += f'{i+1}'
        for face_of_body in body:
            gemotry_text += f' {face_of_body}'
        gemotry_text += ' density 1 volume 1\n'
    gemotry_text += '\n'

    gemotry_text += 'read\n'  # additional commands to to Surface Evolver
    gemotry_text += 'N\n'  # Set target volume to actual volume
    gemotry_text += 'set face color 3 where fixed\n'
    gemotry_text += 'set edge color 4 where fixed\n'

    return gemotry_text, volumes_of_mesh, average_edge_length
