import Rhino
import math


TOLERANCE = 1e-5

def find_mesh_faces_on_brep(mesh, brep):
    mesh_faces_on_brep = []
    brep_bbox = brep.GetBoundingBox(False)
    for brep_face in brep.Faces:
        got_plane, plane = brep_face.TryGetPlane()
        if not got_plane:
            face_bbox = brep_face.GetBoundingBox(False)
            raise(AssertionError, f"brep bounded between {tuple(face_bbox.Min())} and {tuple(face_bbox.Max())} is not plannar.")

        for i, mesh_face in enumerate(mesh.Faces):
            face_center = mesh.Faces.GetFaceCenter(i)
            closest = brep_bbox.ClosestPoint(face_center)
            if ( 
                abs(closest.DistanceToSquared(face_center)) < (TOLERANCE**2 * brep_bbox.Area) and # TODO: Make tolerance relative to bbox size
                    plane.Normal.IsParallelTo(mesh.FaceNormals[i])
            ):
                mesh_faces_on_brep.append(i)
        
    return mesh_faces_on_brep

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

    number_of_edges = edges.Count
    number_of_verts = verts.Count

    edges_on_interface = [False] * number_of_edges
    faces_of_each_body_flat = [0] * faces.Count
    interface_pairs = set(tuple(_) for _ in mesh.Faces.GetClashingFacePairs(0))
    for pair in interface_pairs:
        faces_of_each_body_flat[max(pair)] = - (min(pair)+1)
        for i in edges.GetEdgesForFace(max(pair)):
            edges_on_interface[i] = True

    number_of_faces = sum([i==0 for i in faces_of_each_body_flat])

    se_verts = verts
    se_edges = [tuple(edges.GetTopologyVertices(i)) for i in range(number_of_edges)]
    se_faces = [()] * number_of_faces
    se_bodies = [0] * number_of_bodies
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
        faces_to_make_fixed = find_mesh_faces_on_brep(mesh, fixed)
        for global_face_index in faces_to_make_fixed:
            fixed_face_index = abs(faces_of_each_body_flat[global_face_index]) - 1
            if faces_of_each_body_flat[global_face_index] < 0: continue
            fixed_faces[fixed_face_index] = True
            for i in edges.GetEdgesForFace(global_face_index):
                fixed_edges[i] = True
            for i in verts.IndicesFromFace(global_face_index):
                fixed_verts[i] = True

    average_edge_length = sum([edges.EdgeLine(i).Length for i in range(number_of_edges)]) / number_of_edges
    return se_verts, se_edges, se_faces, se_bodies, fixed_verts, fixed_edges, fixed_faces, edges_on_interface, volumes_of_mesh, average_edge_length

def get_mesh_topology_for_fe(meshes, fixed_meshes, ideal_curves, approx_curves):
    se_verts, se_edges, se_faces, se_bodies, fixed_verts, fixed_edges, fixed_faces, edges_on_interface, volumes_of_mesh, average_edge_length = extract_se_data_from_mesh(meshes, fixed_meshes)

    gemotry_text = ""
    gemotry_text += 'define edge attribute interface integer\n'

    # Write boundary constraints
    for i, curve in enumerate(ideal_curves):
        success, circle = curve.TryGetCircle()
        assert success, f"Could not convert boundary curve {i+1} to circle"

        radius = circle.Radius
        center = circle.Center
        x_axis = circle.Plane.XAxis
        y_axis = circle.Plane.YAxis
        gemotry_text += f'boundary {i+1} parameters 1\n'
        for j in range(3):
            gemotry_text += f'x{j+1}: {center[j]} + {radius} * ( {x_axis[j]} * cos(p1) + {y_axis[j]} * sin(p1) )\n'
        gemotry_text += f'\n'

    # Write vertices
    vert_on_boundary = [0] * se_verts.Count
    gemotry_text += 'vertices\n'
    for i, v in enumerate(se_verts):
        on_boundary = False
        for j, curve in enumerate(approx_curves):
            ideal = ideal_curves[j]
            success, t = curve.ClosestPoint(v)
            assert success
            if (abs(curve.PointAt(t).DistanceTo(v)) < TOLERANCE * curve.GetLength()):
                success, t = ideal.ClosestPoint(v)
                assert success
                on_boundary = True
                # We encode the presence of a vertex on a boundry curve in binary representation.
                # The `1 << j` operation shifts the number 1 j bits to the left.
                # Because Python integer has no fixed size, we can represent any number of combination
                # limited only by the machine's memory.
                # This uniquely defines on what curves a certain vertex is on.
                vert_on_boundary[i] += (1 << j)
                gemotry_text += f"{i+1} {t * 2 * math.pi / ideal.Domain.Length}"
                gemotry_text += f' boundary {j+1}'
                break
        if not on_boundary:
            gemotry_text += f"{i+1} {v.X:.2f} {v.Y:.2f} {v.Z:.2f}"
        if fixed_verts[i]:
            gemotry_text += ' fixed'
        gemotry_text += '\n'
    gemotry_text += '\n'
        
    # Write edges
    gemotry_text += 'edges\n'
    for i, edge in enumerate(se_edges):
        v0, v1 = edge
        gemotry_text += f"{i+1} {v0+1} {v1+1}"
        # if fixed_edges[i]:
        #     gemotry_text += ' fixed'
        if edges_on_interface[i]:
            gemotry_text += ' interface 1'
        # Recall that `vert_on_boundary` hold binary encoding of which boundary curve does a certain
        # vertex belongs to.
        # The `&` operation does a bitwise-and of the values.
        # Wherever two entires have matching bits it means that they are both on that edge.
        # Here, they should share not more than 1 bit, otherwise both vertices share multiple edges,
        # and hence they coincide.
        # We check this using the assertion with the bitwise-xor operation, `^`.
        # We xor the result of the previous bit-and with a binary encoding of the boundary
        # we found using the `bit_length` method.
        bitand_verts = vert_on_boundary[v0] & vert_on_boundary[v1]
        if (bitand_verts != 0):
            curve_number = bitand_verts.bit_length()
            assert (not (bitand_verts ^ (1<<(curve_number-1)))), f"Vertices {v0} and {v1} share more than a single boundary curve"
            gemotry_text += f' fixed boundary {curve_number}'
        gemotry_text += '\n'
    gemotry_text += '\n'

    # Write faces
    gemotry_text += 'faces\n'
    for i, face in enumerate(se_faces):
        gemotry_text += f'{i+1}'
        for edge_of_face in face:
            gemotry_text += f' {edge_of_face}'
        if fixed_faces[i]:
            gemotry_text += ' fixed no_refine'
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
    gemotry_text += 'set edge color green where interface == 1\n'
    gemotry_text += 'set face color 3 where fixed\n'
    gemotry_text += 'set edge color 4 where fixed\n'

    return gemotry_text, volumes_of_mesh, average_edge_length
