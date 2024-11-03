import logging
import datetime
from pathlib import Path

import numpy as np
from pxr import Sdf, UsdGeom, Usd

from grill import cook, names, usd as gusd
from grill.tokens import ids


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

names.UsdAsset.DEFAULT_SUFFIX = "usda"


def _make_plane(mesh, width, depth):
    # https://github.com/marcomusy/vedo/issues/86
    # https://blender.stackexchange.com/questions/230534/fastest-way-to-skin-a-grid
    x_ = np.linspace(-(width / 2), width / 2, width)
    z_ = np.linspace(depth / 2, - depth / 2, depth)
    X, Z = np.meshgrid(x_, z_)
    x = X.ravel()
    z = Z.ravel()
    y = np.zeros_like(x)
    points = np.stack((x, y, z), axis=1)
    xmax = x_.size
    zmax = z_.size
    faceVertexIndices = np.array([
        (i + j * xmax, i + j * xmax + 1, i + 1 + (j + 1) * xmax, i + (j + 1) * xmax)
        for j in range(zmax - 1) for i in range(xmax - 1)
    ])

    faceVertexCounts = np.full(len(faceVertexIndices), 4)
    mesh.GetPointsAttr().Set(points)
    mesh.GetFaceVertexCountsAttr().Set(faceVertexCounts)
    mesh.GetFaceVertexIndicesAttr().Set(faceVertexIndices)


class MiniAsset(names.UsdAsset):
    drop = ('code', 'media', 'area', 'stream', 'step', 'variant', 'part')


cook.UsdAsset = MiniAsset


def main():
    token = cook.Repository.set(Path(__file__).parent / "broadcast")
    stage = cook.fetch_stage(MiniAsset.get_default())
    width = 10
    depth = 8

    # 1.1 Model kingdom is for "all things that exist" in the universe.
    _model_fields = {ids.CGAsset.kingdom.name: "Model"}
    with cook.taxonomy_context(stage):
        # 1.2 These are the "foundational" objects that other taxa inherit from.
        element = cook.define_taxon(stage, "Elements", id_fields=_model_fields)
        UsdGeom.Xform.Define(stage, element.GetPath())

        buildings, country = [
            cook.define_taxon(stage, name, references=(element,))
            for name in ("Buildings", "Blocks",)
        ]

    window = cook.create_unit(element, 'Window')

    building = cook.create_unit(buildings, 'Multi_Story_Building')
    block_with_inherited_windows, block_with_specialized_windows, block = cook.create_many(country, ('Block_With_Inherited_Windows', 'Block_With_Specialized_Windows', 'Block'))

    with cook.unit_context(window):
        geom_root = stage.DefinePrim(window.GetPath().AppendChild("Geom"))
        UsdGeom.Gprim(geom_root).CreateDisplayColorPrimvar().Set([(0.6, 0.8, 0.9)])

        mesh = UsdGeom.Mesh.Define(stage, geom_root.GetPath().AppendChild("Grid"))
        _make_plane(mesh, width, depth)
        mesh.GetDoubleSidedAttr().Set(True)
        mesh.GetPrim().SetDocumentation("Main mesh where Golden Krone exists")

        xform = UsdGeom.XformCommonAPI(mesh)
        xform.SetRotate((90,0,90))

        color_options = {
            "red": (gusd._GeomPrimvarInfo.CONSTANT, lambda x: [(1,0,0)]),
            "blue": (gusd._GeomPrimvarInfo.CONSTANT, lambda x: [(0,0,1)]),
        }
        geoms_with_color = [gprim for prim in Usd.PrimRange(geom_root) if (gprim := UsdGeom.Gprim(prim))]

        color_set = window.GetVariantSets().AddVariantSet("color")

        for option_name, (primvar_meta, color_caller) in color_options.items():
            with Sdf.ChangeBlock():
                color_set.AddVariant(option_name)
                color_set.SetVariantSelection(option_name)
            with Sdf.ChangeBlock(), gusd.edit_context(color_set, cook.unit_asset(window)):
                # golden_color_path = Sdf.Path.absoluteRootPath.AppendPath(option_name)
                # golden_color.OverridePrim(golden_color_path)
                # arc = Sdf.Reference(golden_color.GetRootLayer().identifier, golden_color_path)
                # window.GetReferences().AddReference(arc)
                # with gusd.edit_context(arc, window):
                interpolation = primvar_meta.interpolation()
                for geom in geoms_with_color:
                    if UsdGeom.Curves(geom) and primvar_meta in {gusd._GeomPrimvarInfo.FACE_VARYING}:
                        # Curves do not support faceVarying interpolation
                        continue
                    color_var = geom.GetDisplayColorPrimvar()
                    color_var.SetInterpolation(interpolation)
                    color_size = primvar_meta.size(geom)
                    color_var.SetElementSize(color_size)
                    color_var.Set(color_caller(color_size))
        color_set.ClearVariantSelection()  # Warning: Stage save only considers currently used layers, so layers that are only behind a variant selection might not be saved.

    with cook.unit_context(building):
        # romania_geom = cook.fetch_stage(romania_asset_name.get(part="Geom"))
        # romania_geom.SetDefaultPrim(romania_geom.DefinePrim(cook._UNIT_ORIGIN_PATH))
        # romania_payload = Sdf.Payload(romania_geom.GetRootLayer().identifier)
        # building.GetPayloads().AddPayload(romania_payload)
        instancer_path = (romania_path:=building.GetPath()).AppendPath("Windows")
        targets = []
        selections = ("", *color_set.GetVariantNames())
        prototypes_paths = [
            instancer_path.AppendPath(
                (name := window.GetName()) if not selection else f"{name}_{selection}"
            ).MakeRelativePath(romania_path) for selection in selections
        ]
        prototypes = cook.spawn_many(building, window, prototypes_paths)
        with Sdf.ChangeBlock():
            for prototype, selection in zip(prototypes, selections, strict=True):
                if selection:
                    prototype.GetVariantSet("color").SetVariantSelection(selection)
                relpath = prototype.GetPath().MakeRelativePath(instancer_path)
                targets.append(relpath)

        buildings = UsdGeom.PointInstancer.Define(stage, instancer_path)
        X_size = 4
        Z_size = 3
        Y_size = Z_size * 7
        X = np.linspace(0, (X_size*width)-width, X_size)
        Z = np.linspace(0, (Z_size*depth*2)-depth, Z_size)
        Y = np.linspace(0, Y_size, Z_size)
        xx, yy, zz = np.meshgrid(X, Y, Z)
        points = np.stack((xx.ravel(), yy.ravel(), zz.ravel()), axis=1)
        with Sdf.ChangeBlock():
            buildings.GetPositionsAttr().Set(points)
            for target in targets:
                buildings.GetPrototypesRel().AddTarget(target)
            buildings.GetProtoIndicesAttr().Set(
                np.random.choice(range(len(buildings.GetPrototypesRel().GetTargets())), size=len(points))
            )

    instancer_tx = int(6 * X_size)
    instancer_ty = int(2 * Y_size)

    for i, top_country in enumerate((block_with_inherited_windows, block_with_specialized_windows, block)):
        with cook.unit_context(top_country):
            paths = (
                "Building1",
                "Building2",
                "Building3",
                "Building4",
            )
            transforms = (
                (-instancer_tx * (i + 1), instancer_ty * (i + 1), 1),
                (instancer_tx * (i + 1), instancer_ty * (i + 1), 1),
                (-instancer_tx * (i + 1), -instancer_ty * (i + 1), 1),
                (instancer_tx * (i + 1), -instancer_ty * (i + 1), 1),
            )
            instances = cook.spawn_many(top_country, building, paths)

            specializing = i in {0, 1}
            if specializing:
                specialized_prim = instances[0].GetPrimAtPath(prototypes_paths[0])
                edit_method = cook.specialized_context if i == 1 else cook.inherited_context
                broadcast_color = "red" if i == 1 else "blue"
                with edit_method(specialized_prim, top_country):
                    specialized_prim.GetVariantSet("color").SetVariantSelection(broadcast_color)

            with Sdf.ChangeBlock():
                for r_inst, value in zip(instances, transforms, strict=True):
                    UsdGeom.XformCommonAPI(r_inst).SetTranslate(value)
                    # Workflow: if we're going to broadcast changes, don't instance the point instancer.
                    if specializing:
                        ########################
                        # Note: when making changes on instances, try to always use variant sets to reduce total prototype count
                        # (using specializes or inhertis create additional localized opinions which increase amount of prototypes)
                        # for child in r_inst.GetPrimAtPath("Buildings").GetChildren():
                        #     print(f"{child=}")
                        #     child.GetVariantSet("color").SetVariantSelection("spectrum_vertex")
                        # ########################
                        # local_stage = Usd.Stage.Open(cook.unit_asset(top_country))
                        # # specializes path to component level can't be mapped via edit target
                        # specialized = local_stage.OverridePrim("/Specialized/Model/Place/Window")
                        # specialized.GetVariantSet("color").SetVariantSelection("spectrum_vertex")
                        ####### Uncomment these lines to ensure specialized takes effect in deterministic ways when instancing!!!! ######
                        # local_stage.CreateClassPrim("/__temp")
                        # r_inst.GetReferences().AddInternalReference("/__temp")
                        # # ####### Uncomment these lines to ensure specialized takes effect in deterministic ways when instancing!!!! ######
                        r_inst.SetInstanceable(True)
                        ...
                    else:
                        ...
                        r_inst.SetInstanceable(True)

    cook.Repository.reset(token)
    return stage



if __name__ == "__main__":
    import shutil
    import cProfile
    source_root = Path(__file__).parent
    build_root = source_root / "broadcast"
    shutil.rmtree(build_root, True)

    logging.basicConfig(level=logging.DEBUG)

    start = datetime.datetime.now()
    pr = cProfile.Profile()
    pr.enable()
    stage = pr.runcall(main)
    pr.disable()
    pr.dump_stats(str(Path(__file__).parent / "stats_no_init_name.log"))
    end = datetime.datetime.now()
    print(f"Total time: {end - start}")
    stage.Save()
    # usdzip -a "C:\Users\Christian\OneDrive\write\proyectos\self\g_instances\broadcast\City-Entry-Assembly.1.usda" "C:\Users\Christian\OneDrive\write\proyectos\self\g_instances\broadcast_nested_instances.usdz"
    # usdzip -a "C:\Users\Christian\OneDrive\read\cg\usd\paint\output_old.usd" "C:\Users\Christian\OneDrive\read\cg\usd\paint\paint2.usdz"
    # usdzip -a "C:\Users\Christian\OneDrive\read\cg\usd\paint\output_leah.usd" "C:\Users\Christian\OneDrive\read\cg\usd\paint\paint_leah.usdz"
    # usdzip -a "C:\Users\Christian\OneDrive\read\cg\usd\paint\output_novc2_animated.usd" "C:\Users\Christian\OneDrive\read\cg\usd\paint\paint_novc2.usdz"