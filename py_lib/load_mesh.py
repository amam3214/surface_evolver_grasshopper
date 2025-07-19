import Rhino
from collections import defaultdict


def extract_se_data_from_mesh(mesh, fixed_meshes):
    assert(type(mesh) == Rhino.Geometry.Mesh)

    verts = mesh.Vertices
    edges = mesh.TopologyEdges
    faces = mesh.Faces

    number_of_verts = verts.Count
    number_of_edges = edges.Count
    number_of_faces = faces.Count

    se_verts = verts
    se_edges = [tuple(edges.GetTopologyVertices(i)) for i    in range(number_of_edges)]
    se_faces = [tuple(edges.GetEdgesForFace(i))     for i    in range(number_of_faces)]

    face_edge_to_flip = []
    for i, face in enumerate(faces):
        edge_to_flip = [0, 0, 0]
        face_by_edges = se_faces[i]
        verts_of_edges = [se_edges[i] for i in face_by_edges]
        face_by_verts = (face.A, face.B, face.C)
        vert_pairs_of_face = list(zip(face_by_verts, face_by_verts[1:] + face_by_verts[:1]))
        for j, pair in enumerate(verts_of_edges):
            if pair not in vert_pairs_of_face:
                edge_to_flip[j] = 1

        face_edge_to_flip.append(tuple(edge_to_flip))

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
            fixed_face_index = p.I if p.I<number_of_faces else p.J
            fixed_faces[fixed_face_index] = True
            for i in se_faces[fixed_face_index]:
                fixed_edges[i] = True
            face = faces.GetFace(fixed_face_index)
            fixed_verts[face.A] = True
            fixed_verts[face.B] = True
            fixed_verts[face.C] = True

    average_edge_length = sum([edges.EdgeLine(i).Length for i in range(number_of_edges)]) / number_of_edges
    return se_verts, se_edges, se_faces, face_edge_to_flip, fixed_verts, fixed_edges, fixed_faces, average_edge_length

def get_mesh_topology_for_fe(mesh, fixed_meshes):
    se_verts, se_edges, se_faces, face_edge_to_flip, fixed_verts, fixed_edges, fixed_faces, average_edge_length = extract_se_data_from_mesh(mesh, fixed_meshes)
    gemotry_text = ""
    # Write vertices
    gemotry_text += 'vertices\n'
    mesh_bbox = mesh.GetBoundingBox(False)
    min_X, min_Y, min_Z = mesh_bbox.Min
    max_X, max_Y, max_Z = mesh_bbox.Max
    for i, v in enumerate(se_verts):
        gemotry_text += f"{i+1} {v.X + (max_X - min_X) * 1.1:.2f} {v.Y:.2f} {v.Z:.2f}"
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
        for j, edge_of_face in enumerate(face):
            gemotry_text += f' {(edge_of_face + 1) * (-1)**face_edge_to_flip[i][j]}'
        if fixed_faces[i]:
            gemotry_text += ' fixed'
        gemotry_text += '\n'
    gemotry_text += '\n'

    # Write bodies
    gemotry_text += 'bodies\n'
    gemotry_text += '1 '
    face_index = 1
    for i in range(len(se_faces)):
        gemotry_text += f"{i+1} "
    
    gemotry_text += 'density 1 volume 1\n\n'

    gemotry_text += 'read\n'  # additional commands to to Surface Evolver
    gemotry_text += 'N\n'  # Set target volume to actual volume
    gemotry_text += 'set edge color 4 where fixed\n'

    return gemotry_text, (max_X - min_X), (max_Y - min_Y), (max_Z - min_Z), average_edge_length
