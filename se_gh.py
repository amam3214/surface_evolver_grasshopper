import os
import math
import Rhino
import subprocess

# TODO:
# - Add the interface feature and multibodies
# - Add stuff, if missing, to the read section of the code gen


TOLERANCE = 1e-5
SPACE_DIMENSION = 3

def main(
    bodies,
    surface_bcs,
    ideal_bcs,
    apprx_bcs,
    base_path,
):
    # set up paths
    evolver_path = os.path.join(base_path, r"evolver.exe")
    tmp_path = os.path.join(base_path, r"tmp.fe")
    dmp_path = os.path.join(base_path, r"dmp.fe")
    stl_path = os.path.join(base_path, r"stl.fe")
    if not os.path.isfile(evolver_path):
        raise FileExistsError(f"Could not find evolver executable at: {evolver_path}")

    # set up buffer for evolver code
    se_code = []
    get_evolver_data(se_code, bodies, surface_bcs, ideal_bcs, apprx_bcs)

    with open(tmp_path, "w") as tmp:
        tmp.write(''.join(se_code))

    # subprocess.run([evolver_path, tmp_path])

    apprx_bcs = match_boundaries(ideal_bcs, apprx_bcs)
    return

def get_evolver_data(se_code, bodies, surface_bcs, ideal_bcs, apprx_bcs):
    brep = Rhino.Geometry.Brep.MergeBreps(bodies, Rhino.RhinoMath.ZeroTolerance)
    verts = brep.Vertices
    edges = brep.Edges
    faces = brep.Faces

    # fixed
    fixed_verts = [0] * verts.Count
    fixed_edges = [0] * edges.Count
    fixed_faces = [0] * faces.Count
    for i, f in enumerate(faces):
        duplicate_face = f.DuplicateFace(False)
        for surface in surface_bcs:
            face_on_surface = True
            for v in duplicate_face.Vertices:
                closest = surface.ClosestPoint(v.Location)
                face_on_surface = face_on_surface and (abs(v.Location.DistanceTo(closest)) < TOLERANCE * math.sqrt(duplicate_face.GetArea()))

            if face_on_surface:
                fixed_faces[i] = 1
                edge_indices_of_face = f.AdjacentEdges()
                for edge_index in edge_indices_of_face:
                    fixed_edges[edge_index] = 1
                    fixed_verts[edges[edge_index].StartVertex.VertexIndex] = 1
                    fixed_verts[edges[edge_index].EndVertex.VertexIndex] = 1
                break

    # interfaces
    interface_edges = [0] * edges.Count

    # code gen ##############################################
    # defines
    se_code.append("define edge attribute interface integer\n")

    # boundaries
    for i, curve in enumerate(ideal_bcs):
        success, circle = curve.TryGetCircle()
        assert success, f"Could not convert boundary curve {i+1} to circle"

        radius = circle.Radius
        center = circle.Center
        x_axis = circle.Plane.XAxis
        y_axis = circle.Plane.YAxis
        se_code.append(f"boundary {i+1} parameters 1\n")
        for j in range(SPACE_DIMENSION):
            se_code.append(f"x{j+1}: {center[j]} + {radius} * ( {x_axis[j]} * cos(p1) + {y_axis[j]} * sin(p1) )\n")
        se_code.append('\n')

    # vertices
    vert_boundary_encoding = [0] * verts.Count
    se_code.append("vertices\n")
    for i, v_brep in enumerate(verts):
        v = v_brep.Location
        on_boundary = False

        for j, curve in enumerate(apprx_bcs):
            ideal = ideal_bcs[j]
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
                vert_boundary_encoding[i] += (1 << j)
                se_code.append(f"{i+1} {t * 2 * math.pi / ideal.Domain.Length}")
                se_code.append(f" boundary {j+1}")
                break
        if not on_boundary:
            se_code.append(f"{i+1:4d} {v.X:.8f} {v.Y:.8f} {v.Z:.8f}")
        if fixed_verts[i]:
            se_code.append(" fixed")
        se_code.append('\n')
    se_code.append('\n')

    # edges
    se_code.append("edges\n")
    for i, e in enumerate(edges):
        v0 = e.StartVertex.VertexIndex
        v1 = e.EndVertex.VertexIndex
        se_code.append(f"{i+1} {v0+1} {v1+1}")
        if interface_edges[i]:
            assert false, "todo"
            se_code.appned(" interface 1")
        # Recall that `vert_boundary_encoding` hold binary encoding of which vertex is on a certain boundary.
        # The `&` operation does a bitwise-and of the values.
        # Wherever two entires have matching bits it means that they are both on that edge.
        # Here, they should not share more than 1 bit, otherwise both vertices share multiple edges,
        # and hence they coincide.
        # We check this using the assertion with the bitwise-xor operation, `^`.
        # We xor the result of the previous bit-and with a binary encoding of the boundary
        # we found using the `bit_length` method.
        bitand_verts = vert_boundary_encoding[v0] & vert_boundary_encoding[v1]
        if (bitand_verts != 0):
            curve_number = bitand_verts.bit_length()
            assert (not (bitand_verts ^ (1<<(curve_number-1)))), f"Vertices {v0} and {v1} share more than a single boundary curve"
            se_code.append(f" fixed boundary {curve_number}")
        elif fixed_edges[i]:
            se_code.append(f" fixed")
        se_code.append('\n')
    se_code.append('\n')

    # faces
    se_code.append("faces\n")
    for i, f in enumerate(faces):
        se_code.append(f"{i+1}")
        success, face_plane = f.TryGetPlane()
        assert success
        face_normal = face_plane.Normal
        face_edges = f.AdjacentEdges()
        face_edges_count = len(face_edges)
        trims_vert_pairs = [(t.StartVertex.VertexIndex, t.EndVertex.VertexIndex) for t in f.OuterLoop.Trims]
        edges_vert_pairs = [(edges[j].StartVertex.VertexIndex, edges[j].EndVertex.VertexIndex) for j in f.AdjacentEdges()]

        for j in range(face_edges_count):
            if (trims_vert_pairs[j] == edges_vert_pairs[j]):
                se_code.append(f" {face_edges[j]+1}")
            elif (trims_vert_pairs[j] == edges_vert_pairs[j][::-1]):
                se_code.append(f" -{face_edges[j]+1}")
            else:
                assert False
        if fixed_faces[i]:
                se_code.append(f" fixed")
        se_code.append('\n')
    se_code.append('\n')

    # bodies
    se_code.append("bodies\n")
    se_code.append("1")
    for i, f in enumerate(faces):
        se_code.append(f" {i+1}")
    se_code.append('\n')
    se_code.append('\n')

    # read section
    se_code.append(f"read // Take and run SE commands from this file\n")
    se_code.append("set edge color green where interface == 1\n")
    se_code.append("set face color 3 where fixed\n")
    se_code.append("set edge color 4 where fixed\n")

    se_code.append(f"G 0\n")
    se_code.append(f"set body target {brep.GetVolume()} where id==1\n")
    se_code.append(f"s // open graphic window\nq\n")
    se_code.append(f"\n")
    return

def get_verts_id_of_edge(edge):
    return edges[edge_indices[0]].StartVertex.VertexIndex, edges[edge_indices[0]].EndVertex.VertexIndex

def match_boundaries(ideal_bcs, apprx_bcs):
    assert len(ideal_bcs) == len(apprx_bcs), f"Got different number of ideal ({len(ideal_bcs)}) and apprximate ({len(apprx_bcs)}) boundary curves"

    new_apprx_bcs = []
    for ideal in ideal_bcs:
        length = ideal.GetLength()
        for apprx in apprx_bcs:
            success, p0, p1 = ideal.ClosestPoints(apprx)
            assert success
            if ((p0 - p1).Length < TOLERANCE * length):
                new_apprx_bcs.append(apprx)
                break

    assert len(ideal_bcs) == len(new_apprx_bcs), f"Could not match all apprximate and ideal curves: {len(new_apprx_bcs)}/{len(ideal_bcs)} matched"

    return new_apprx_bcs
