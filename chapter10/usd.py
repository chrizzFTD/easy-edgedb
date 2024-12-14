# https://stackoverflow.com/a/72788936
# https://youtrack.jetbrains.com/issue/PY-50959
# conda create -n edb313 python=3.13
# conda activate edb313
# python -m pip install -e A:\write\code\git\grill
# python -m pip install PySide6 PyOpenGL
# python -m pip install edgedb  (fails on Windows + Python-3.13)
# Fix paths in C:\Users\Christian\AppData\Roaming\JetBrains\PyCharmCE2024.1\options\jdk.table.xml
import contextlib
import logging
import datetime
import itertools
from pathlib import Path

import networkx
import numpy as np

from pxr import Sdf, UsdGeom, Usd, Kind, Tf

from grill import cook, names, usd as gusd
from grill.tokens import ids

_notice_counter = itertools.count()

# Sdf.ChangeBlock = contextlib.nullcontext
def _notify(notice, sender):
    # return
    """
    0:00:00.961997
    1320: Changed: []
    1320: Changed: [Sdf.Path('/Catalogue/Model/Player/EmilSinclair')]

    2023 02 25: Updated to:

    0:00:00.776181  (20% faster)
    309: Changed: []
    309: Changed: [Sdf.Path('/Catalogue/Model/Player/EmilSinclair')]

    2023 11 26

    Start:
        322: notice.GetChangedInfoOnlyPaths()=[]
        322: notice.GetResyncedPaths()=[Sdf.Path('/Catalogue/Model/Person/NewPerson0')]
            Total time: 0:00:01.077525

    End:
        231: notice.GetChangedInfoOnlyPaths()=[]
        231: notice.GetResyncedPaths()=[Sdf.Path('/Catalogue/Model/Person/NewPerson0')]
            Total time: 0:00:00.810436

    --- Without SdfChangeBlock, this would be ---
        1641: notice.GetChangedInfoOnlyPaths()=[Sdf.Path('/Catalogue/Model/Person/NewPerson0')]
        1641: notice.GetResyncedPaths()=[]
            Total time: 0:00:01.154914

    2024 02 22

    for amount=1_000:
        without changeblock:
            Total time: 0:00:13.799406
            Total notices 22621
        with changeblock:
            Total time: 0:00:09.013849
            Total notices 232

    2024 04 25

    for amount=1_000:
        without changeblock:
            Total time: 0:00:13.041650
            Total notices 22621
        with changeblock:
            Total time: 0:00:08.590089
            Total notices 232

    2024 10 27

    for amount=1_000:
        without changeblock:
            Total time: 0:00:10.707131
            Total notices 22621
        with changeblock:
            Total time: 0:00:06.418158
            Total notices 232

    2024 12 14 - Py-3.13 + USD-24.11, added relocates usage and basis curves lineup

    for amount=1_000:
        without changeblock:
            Total time: 0:00:10.674980
            Total notices 22600
        with changeblock:
            Total time: 0:00:06.356973
            Total notices 278
    """
    next(_notice_counter)
    # print(f"{(no:=next(_notice_counter))}: {notice.GetChangedInfoOnlyPaths()=}")
    # print(f"{no}: {notice.GetResyncedPaths()=}")


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

names.UsdAsset.DEFAULT_SUFFIX = "usda"


def _tag_persistent(obj):
    obj.SetAssetInfoByKey("grill:database", True)


def _tag_persistent_target(obj, target):
    obj.SetAssetInfoByKey("grill:target_taxon", target.GetName())


def main():
    token = cook.Repository.set(Path(__file__).parent / "assets")
    stage = cook.fetch_stage(names.UsdAsset.get_default(code='dracula'))

    notice = Tf.Notice.Register(Usd.Notice.ObjectsChanged, _notify, stage)

    # 1. Taxonomy Definition
    with cook.taxonomy_context(stage):
        model_default_color = cook.create_unit(
            cook.define_taxon(stage, "Color", id_fields={ids.CGAsset.kingdom.name: "Shade"}),
            "ModelDefault", label="🎨 Model Default"
        )
        shape_taxon = cook.define_taxon(stage, "Shape", id_fields={ids.CGAsset.kingdom.name: "Geom"})

        geom_plane = cook.create_unit(shape_taxon, "GroundPlane", label="🎲 Ground Plane")
        basis_s, nurbs_s = cook.create_many(shape_taxon, names=["BasisS", "NurbsS"], labels=["🎲 Basis S", "🎲 Nurbs S"])

        basis_lineup = cook.create_unit(shape_taxon, "BasisLineup", label="Basis Lineup")

    # TODO: see if component default actually makes sense, for now need to change it
    # We are going to be re-using the plane
    width = 10  # 10
    depth = 8  # 8

    with Sdf.ChangeBlock():
        for unit in geom_plane, basis_s, nurbs_s, model_default_color, basis_lineup:
            with cook.unit_context(unit):
                Usd.ModelAPI(unit).SetKind(Kind.Tokens.subcomponent)
                if unit == model_default_color:
                    UsdGeom.Gprim(unit).CreateDisplayColorPrimvar().Set([(0.6, 0.8, 0.9)])

    curve_points = [(0, 0, 0), (2, 1, 0), (2, 2, 0), (1, 2.5, 0), (0, 3, 0), (0, 4, 0), (2, 5, 0)]
    max_x_curve = max([point[0] for point in curve_points])
    with cook.unit_context(basis_s):
        basis = UsdGeom.BasisCurves.Define(stage, basis_s.GetPath())
        with Sdf.ChangeBlock():
            basis.GetPointsAttr().Set(curve_points)
            basis.GetCurveVertexCountsAttr().Set([len(curve_points)])

    def set_curve_attrs(curve, type, basis_id, width_interpolation_id, max_width):
        # UsdGeom.XformCommonAPI(curve).SetTranslate(xform)
        with Sdf.ChangeBlock():
            curve.GetTypeAttr().Set(type)
            curve.GetBasisAttr().Set(bezier_types[basis_id])
        width_interpolation_name = widths_interpolation_types[width_interpolation_id].interpolation()
        width_interpolation_size = widths_interpolation_types[width_interpolation_id].size(curve)
        with Sdf.ChangeBlock():
            assert curve.SetWidthsInterpolation(width_interpolation_name)
            assert curve.GetWidthsAttr().Set(
                [
                    (max_width * (i / width_interpolation_size) if width_interpolation_size > 1 else max_width)
                    for i in range(width_interpolation_size)
                ]
            )

    with cook.unit_context(basis_lineup):
        basis_lineup_curves = cook.spawn_many(
            basis_lineup, basis_s,
            paths=[basis_lineup.GetPath().AppendChild(f"Basis_M_{each}") for each in range(depth)],
            labels=[f"Basis M {each}" for each in range(depth)],
        )
        with Sdf.ChangeBlock():
            for each, curve in zip(range(depth), basis_lineup_curves):
                curve = UsdGeom.BasisCurves(curve)
                xform = (0, 0, each - (depth / 2.0))
                UsdGeom.XformCommonAPI(curve).SetTranslate(xform)

    with cook.unit_context(geom_plane):
        gusd._make_plane(UsdGeom.Mesh.Define(stage, geom_plane.GetPath()), width, depth)

    # 1.1 Model kingdom is for "all things that exist" in the universe.
    _model_fields = {ids.CGAsset.kingdom.name: "Model"}
    with cook.taxonomy_context(stage):
        # 1.2 These are the "foundational" objects that other taxa inherit from.
        person, transport, place, ship = [
            cook.define_taxon(stage, name, id_fields=_model_fields)
            for name in ("Person", "LandTransport", "Place", "Ship",)
        ]
        for taxon in (person, place, ship):  # base xformable taxa
            UsdGeom.Xform.Define(stage, taxon.GetPath())

        player = cook.define_taxon(stage, "Player", references=(person, transport))
        non_player, vampire, minor_vampire, crewman, sailor = [
            cook.define_taxon(stage, name, references=(person,))
            for name in ("NonPlayer", "Vampire", "MinorVampire", "Crewman", "Sailor",)
        ]

        city, country, other_place = [
            cook.define_taxon(stage, name, references=(place,))
            for name in ("City", "Country", "OtherPlace",)
        ]

        with Sdf.ChangeBlock():
            # 1.3 Add required taxa properties
            pop_attr = city.CreateAttribute('population', Sdf.ValueTypeNames.Int, custom=False)
            _tag_persistent(pop_attr)

            # TODO: how to add constraints? Useful to catch errors before they hit the database
            #   https://github.com/edgedb/easy-edgedb/blob/master/chapter3/index.md#adding-constraints
            age = person.CreateAttribute('age', Sdf.ValueTypeNames.Int, custom=False)
            _tag_persistent(age)
            age.SetDocumentation("This value must be constrained at the data base / application level since USD does not provide easy constraint mechanisms for values yet.")
            strength = person.CreateAttribute('strength', Sdf.ValueTypeNames.Int, custom=False)
            strength.SetDocumentation("Used to help answer if a person is able to perform some actions (e.g. can this person open a door?)")
            _tag_persistent(strength)
            mn_attr = place.CreateAttribute("modern_name", Sdf.ValueTypeNames.String, custom=False)
            _tag_persistent(mn_attr)

            for taxon, relationships in (
                (person, (('lover', person), ('places_visited', place))),
                (vampire, (('slaves', vampire),)),  # it needs to be a vampire
                (ship, (('sailors', sailor), ('crew', crewman))),
            ):
                for rel_name, target_taxon in relationships:
                    rel = taxon.CreateRelationship(rel_name, custom=False)
                    _tag_persistent(rel)
                    _tag_persistent_target(rel, target_taxon)


            for taxon, set_name, variants in (
                (transport, "Transport", ("Feet", "Train", "HorseDrawnCarriage")),
                # rank is its own separate type in easyedb, but for now we can keep in under sailor unless something else needs to arc from it
                (sailor, "Rank", ("Captain", "FirstMate", "SecondMate", "Cook")),
            ):
                variant_set = taxon.GetVariantSets().AddVariantSet(set_name)
                for variant in variants:
                    variant_set.AddVariant(variant)

    # 2. Create the universe
    budapest, bistritz, munich, london = cook.create_many(
        city, ('Budapest', 'Bistritz', 'Munich', 'London'), ('⛪ Buda-Pesth', '🏰 Bistritz')
    )
    with Sdf.ChangeBlock():
        for city_, population in (budapest, 402706), (london, 3500000), (munich, 230023), (bistritz, 9100):
            with cook.unit_context(city_):
                city_.GetAttribute("population").Set(population)

    golden_krone = cook.create_unit(place, 'GoldenKroneHotel', label='🏨 Golden Krone Hotel')
    castle_dracula = cook.create_unit(other_place, 'CastleDracula', label='🏰 Castle Dracula')
    # 2.1 Create attributes as needed
    with cook.unit_context(castle_dracula):
        doors_strength = castle_dracula.CreateAttribute('doors_strength', Sdf.ValueTypeNames.IntArray, custom=False)
        doors_strength.Set([6, 19, 10])

    romania, inherits_country, specializes_country, unchanged, *__ = cook.create_many(country, ('Romania', 'Inherits', 'Specializes', 'Unchanged', 'Slovakia'))

    jonathan = cook.create_unit(person, 'JonathanHarker', label='👨 Jonathan Harker')
    with cook.unit_context(jonathan):
        jonathan.GetAttribute("strength").Set(5)

    emil = cook.create_unit(player, "EmilSinclair", label="🧔 Emil Sinclair")
    dracula = cook.create_unit(vampire, 'CountDracula', label='🧛 Count Dracula')
    minor_vampires = cook.create_many(minor_vampire, *zip(*[(f'Woman{i}', f'🧛‍♀️ Woman {i}') for i in range(1, 5)]))
    with Sdf.ChangeBlock():
        for each in minor_vampires:
            dracula.GetRelationship("slaves").AddTarget(each.GetPath())

    # mina = cook.create_unit(non_player, 'MinaMurray', label='👩 Mina Murray')
    # lucy = cook.create_unit(non_player, 'LucyWestenra', label='👩‍🦰 Lucy Westenra')
    mina, lucy, arthur, renfield, *__ = cook.create_many(
        non_player,
        ('MinaMurray', 'LucyWestenra', 'ArthurHolmwood', 'Renfield', 'JohnSeward', 'QuinceyMorris'),
        ('👩 Mina Murray', '👩‍🦰 Lucy Westenra')
    )
    with Sdf.ChangeBlock():
        arthur.GetRelationship('lover').AddTarget(lucy.GetPath())
        lucy.GetRelationship("lover").AddTarget(arthur.GetPath())

        with cook.unit_context(renfield):
            renfield.GetAttribute("strength").Set(10)

        mina.GetRelationship("lover").AddTarget(jonathan.GetPath())
        jonathan.GetRelationship("lover").AddTarget(mina.GetPath())
    with cook.unit_context(bistritz):
        spawned = cook.spawn_many(
            bistritz,
            golden_krone,
            (golden_krone.GetName(), "Deeper/Nested/Golden1", "Deeper/Nested/Golden2", "Deeper/Nested/Golden3")
        )
        with Sdf.ChangeBlock():
            bistritz.GetAttribute("modern_name").Set('Bistrița')
            for each, transform in zip(
                    spawned,
                    ((2, 15, 6), (-4, 5, 1), (-4, -10, 1), (0, 10, -5)),
                    strict=True,
            ):
                UsdGeom.XformCommonAPI(each).SetTranslate(transform)

        # spawned.GetVariantSet("color").SetVariantSelection("constant")
        # b_stage = Usd.Stage.Open(cook.unit_asset(bistritz))
        # specialized = b_stage.OverridePrim("/Specialized/Model/Place/GoldenKroneHotel")
        # specialized.GetVariantSet("color").SetVariantSelection("spectrum_uniform")

    with Sdf.ChangeBlock():
        stage.SetStartTimeCode(0)
        stage.SetEndTimeCode(192)

    from PySide6 import QtGui
    from functools import partial
    from grill.views._attributes import _random_colors, _color_spectrum

    _color_spectrum = partial(_color_spectrum, QtGui.QColor.fromHsvF(0, 1, 1), QtGui.QColor.fromHsvF(1, 1, 1))

    golden_asset_name = names.UsdAsset(Usd.ModelAPI(golden_krone).GetAssetIdentifier().path)
    # golden_asset_name.suffix = "usd"
    with cook.unit_context(golden_krone):
        # idea: chain contexts to a specific prim, composition arc and a layer?
        # unit context X -> add geom payload -> add prims A, B
        #               `-> add variant sets -> add color to created prims A, B (same python objects)
        golden_geom = cook.fetch_stage(golden_asset_name.get(part="Geom"))
        golden_shade = cook.fetch_stage(golden_asset_name.get(part="Shade"))
        golden_shade.GetRootLayer().ImportFromString(
"""#usda 1.0
(
    defaultPrim = "Origin"
)

over "Origin" (
    prepend apiSchemas = ["MaterialBindingAPI"]
)
{}
""")
# {
#     rel material:binding = </Origin/materials/mtlxmaterial>
#
#     def Scope "materials"
#     {
#         def Material "mtlxmaterial" (
#             customData = {
#                 int[] HoudiniPrimEditorNodes = [15]
#             }
#             prepend inherits = </__class_mtl__/mtlxmaterial>
#         )
#         {
#             token outputs:mtlx:displacement.connect = </Origin/materials/mtlxmaterial/mtlxdisplacement.outputs:out>
#             token outputs:mtlx:surface.connect = </Origin/materials/mtlxmaterial/mtlxstandard_surface.outputs:out>
#             token outputs:surface.connect = </Origin/materials/mtlxmaterial/mtlxstandard_preview.outputs:surface>
#
#             def Shader "mtlxstandard_surface" (
#                 customData = {
#                     bool HoudiniHasAutoPreviewShader = 1
#                 }
#             )
#             {
#                 uniform token info:id = "ND_standard_surface_surfaceshader"
#                 float inputs:base (
#                     customData = {
#                         dictionary HoudiniPreviewTags = {
#                             double default_value = 1
#                             string ogl_diff_intensity = "1"
#                         }
#                     }
#                 )
#                 color3f inputs:base_color (
#                     customData = {
#                         dictionary HoudiniPreviewTags = {
#                             double3 default_value = (0.8, 0.8, 0.8)
#                             string ogl_diff = "1"
#                         }
#                     }
#                 )
#                 color3f inputs:base_color.connect = </Origin/materials/mtlxmaterial/mtlxUsdPrimvarReader1.outputs:out>
#                 float inputs:coat (
#                     customData = {
#                         dictionary HoudiniPreviewTags = {
#                             double default_value = 0
#                             string ogl_coat_intensity = "1"
#                         }
#                     }
#                 )
#                 float inputs:coat_roughness = 0 (
#                     customData = {
#                         dictionary HoudiniPreviewTags = {
#                             double default_value = 0.1
#                             string ogl_coat_rough = "1"
#                         }
#                     }
#                 )
#                 float inputs:emission (
#                     customData = {
#                         dictionary HoudiniPreviewTags = {
#                             double default_value = 0
#                             string ogl_emit_intensity = "1"
#                         }
#                     }
#                 )
#                 float inputs:emission.connect = </Origin/materials/mtlxmaterial/cubic_red.outputs:out>
#                 color3f inputs:emission_color (
#                     customData = {
#                         dictionary HoudiniPreviewTags = {
#                             double3 default_value = (1, 1, 1)
#                             string ogl_emit = "1"
#                         }
#                     }
#                 )
#                 color3f inputs:emission_color.connect = </Origin/materials/mtlxmaterial/mtlxUsdPrimvarReader1.outputs:out>
#                 float inputs:metalness (
#                     customData = {
#                         dictionary HoudiniPreviewTags = {
#                             double default_value = 0
#                             string ogl_metallic = "1"
#                         }
#                     }
#                 )
#                 float inputs:sheen_roughness = 0
#                 float inputs:specular (
#                     customData = {
#                         dictionary HoudiniPreviewTags = {
#                             double default_value = 1
#                             string ogl_spec_intensity = "1"
#                         }
#                     }
#                 )
#                 color3f inputs:specular_color (
#                     customData = {
#                         dictionary HoudiniPreviewTags = {
#                             double3 default_value = (1, 1, 1)
#                             string ogl_spec = "1"
#                         }
#                     }
#                 )
#                 float inputs:specular_IOR (
#                     customData = {
#                         dictionary HoudiniPreviewTags = {
#                             double default_value = 1.5
#                             string ogl_ior = "1"
#                         }
#                     }
#                 )
#                 float inputs:specular_roughness (
#                     customData = {
#                         dictionary HoudiniPreviewTags = {
#                             double default_value = 0.2
#                             string ogl_rough = "1"
#                         }
#                     }
#                 )
#                 float inputs:transmission (
#                     customData = {
#                         dictionary HoudiniPreviewTags = {
#                             double default_value = 0
#                             string ogl_transparency = "1"
#                         }
#                     }
#                 )
#                 float inputs:transmission.connect = </Origin/materials/mtlxmaterial/compute_eulers_blue.outputs:out>
#                 color3f inputs:transmission_color.connect = </Origin/materials/mtlxmaterial/mtlxUsdPrimvarReader1.outputs:out>
#                 token outputs:out
#             }
#
#             def Shader "mtlxUsdPrimvarReader1"
#             {
#                 uniform token info:id = "ND_UsdPrimvarReader_vector3"
#                 string inputs:varname = "displayColor"
#                 vector3f outputs:out
#             }
#
#             def Shader "compute_eulers_blue"
#             {
#                 uniform token info:id = "ND_add_float"
#                 float inputs:in1 = 1
#                 float inputs:in1.connect = </Origin/materials/mtlxmaterial/negative_eulers.outputs:out>
#                 float inputs:in2 = 1
#                 float outputs:out
#             }
#
#             def Shader "negative_eulers"
#             {
#                 uniform token info:id = "ND_multiply_float"
#                 float inputs:in1.connect = </Origin/materials/mtlxmaterial/eulers_power.outputs:out>
#                 float inputs:in2 = -1
#                 float outputs:out
#             }
#
#             def Shader "eulers_power"
#             {
#                 uniform token info:id = "ND_power_float"
#                 float inputs:in1 = 2.7182
#                 float inputs:in2.connect = </Origin/materials/mtlxmaterial/negative_blue.outputs:out>
#                 float outputs:out
#             }
#
#             def Shader "negative_blue"
#             {
#                 uniform token info:id = "ND_multiply_float"
#                 float inputs:in1.connect = </Origin/materials/mtlxmaterial/mult_blue.outputs:out>
#                 float inputs:in2 = -1
#                 float outputs:out
#             }
#
#             def Shader "mult_blue"
#             {
#                 uniform token info:id = "ND_multiply_float"
#                 float inputs:in1.connect = </Origin/materials/mtlxmaterial/mtlxseparate3c1.outputs:outb>
#                 float inputs:in2 = 3.6
#                 float outputs:out
#             }
#
#             def Shader "mtlxseparate3c1"
#             {
#                 uniform token info:id = "ND_separate3_color3"
#                 color3f inputs:in.connect = </Origin/materials/mtlxmaterial/mtlxUsdPrimvarReader1.outputs:out>
#                 float outputs:outb
#                 float outputs:outr
#             }
#
#             def Shader "cubic_red"
#             {
#                 uniform token info:id = "ND_power_float"
#                 float inputs:in1.connect = </Origin/materials/mtlxmaterial/rerange_red.outputs:out>
#                 float inputs:in2 = 3
#                 float outputs:out
#             }
#
#             def Shader "rerange_red"
#             {
#                 uniform token info:id = "ND_divide_float"
#                 float inputs:in1.connect = </Origin/materials/mtlxmaterial/limit_red.outputs:out>
#                 float inputs:in2 = 0.3
#                 float outputs:out
#             }
#
#             def Shader "limit_red"
#             {
#                 uniform token info:id = "ND_add_float"
#                 float inputs:in1.connect = </Origin/materials/mtlxmaterial/mtlxseparate3c1.outputs:outr>
#                 float inputs:in2 = -0.7
#                 float outputs:out
#             }
#
#             def Shader "mtlxdisplacement"
#             {
#                 uniform token info:id = "ND_displacement_float"
#                 token outputs:out
#             }
#
#             def Shader "mtlxstandard_preview" (
#                 customData = {
#                     bool HoudiniIsAutoCreatedShader = 1
#                 }
#             )
#             {
#                 uniform token info:id = "UsdPreviewSurface"
#                 float inputs:clearcoatRoughness = 0
#                 color3f inputs:diffuseColor = (0.8, 0.8, 0.8)
#                 float inputs:roughness = 0.2
#                 color3f inputs:specularColor = (1, 1, 1)
#                 token outputs:surface
#             }
#         }
#     }
# }
# """
#         )
        # TODO: let's place payload on the root of the unit
        golde_geom_default_prim = golden_geom.DefinePrim(cook._UNIT_ORIGIN_PATH)
        payload = Sdf.Payload(cook.asset_identifier(golden_geom.GetRootLayer().identifier))
        shade_payload = Sdf.Payload(cook.asset_identifier(golden_shade.GetRootLayer().identifier))

        # Create a "Geom" prim specializing from the model_default_color, which is a subcomponent unit.
        geom_root = cook.spawn_unit(golden_krone, model_default_color, "Geom", label="Geom")
        # geom_root.SetInstanceable(False)  # by default, spawning a unit makes it instanceable.
        with Sdf.ChangeBlock():
            golden_geom.SetDefaultPrim(golde_geom_default_prim)
            geom_root.GetPayloads().AddPayload(payload)
            golden_krone.GetPayloads().AddPayload(shade_payload)

        with gusd.edit_context(payload, geom_root):
            bezier_types = ("bezier", "bspline", "catmullRom")
            widths_interpolation_types = tuple(i for i in gusd._GeomPrimvarInfo if i not in {gusd._GeomPrimvarInfo.UNIFORM, gusd._GeomPrimvarInfo.FACE_VARYING})
            normal_interpolation_types = gusd._GeomPrimvarInfo.VARYING,
            volume_size = 2

            left_curve_lineup, right_curve_lineup = cook.spawn_many(golden_krone, basis_lineup, paths=[geom_root.GetPath().AppendChild(side) for side in ("Basis_L", "Basis_R")])
            with Sdf.ChangeBlock():
                left_lineup_xform = UsdGeom.Xform.Define(stage, left_curve_lineup.GetPath())
                right_lineup_xform = UsdGeom.Xform.Define(stage, right_curve_lineup.GetPath())
            with Sdf.ChangeBlock():
                # TODO: place lineup relative to the width of the plane, rather than a third of max_x_curve
                UsdGeom.XformCommonAPI(left_lineup_xform).SetTranslate((-width/2 + max_x_curve/3, 0, 0))
                UsdGeom.XformCommonAPI(right_lineup_xform).SetTranslate((width/2 - max_x_curve - max_x_curve/3, 0,0))


            def _rename_hierarchy(root_prim, to_match: str, replace_with: str):
                stage = root_prim.GetStage()
                editor = Usd.NamespaceEditor(stage)
                for prim in list(Usd.PrimRange(root_prim)):
                    if to_match not in prim.GetName():
                        continue
                    # to_rename[prim.GetPath()] = prim.GetParent().GetPath().AppendChild(prim.GetName().replace(to_match, replace_with))
                    editor.MovePrimAtPath(prim.GetPath(), prim.GetParent().GetPath().AppendChild(prim.GetName().replace(to_match, replace_with)))
                    editor.ApplyEdits()

            # Uncomment when namespace editing supports renaming across composition arcs; right now this fails with:
            #   Edit targets that map paths across composition arcs are not currently supported for namespace editing
            # child_paths = [child.GetPath() for child in left_curve_lineup.GetChildren()]
            # editor = Usd.NamespaceEditor(stage)
            # for child_path in child_paths:
            #     editor.MovePrimAtPath(child_path, child_path.GetParentPath().AppendChild(f"{child_path.name}_moved"))
            #     editor.ApplyEdits()
            # In the meantime
            for golden_geom_prim in golden_geom.Traverse():
                if left_curve_lineup.GetName() == golden_geom_prim.GetName():
                    _rename_hierarchy(golden_geom_prim, "_M_", "_L_")
                elif right_curve_lineup.GetName() == golden_geom_prim.GetName():
                    _rename_hierarchy(golden_geom_prim, "_M_", "_R_")
                else:
                    continue

            for each, child in enumerate(left_curve_lineup.GetChildren()):
                curve = UsdGeom.BasisCurves(child)
                set_curve_attrs(
                    curve,
                    type="linear" if each % 2 else "cubic",  # Tried linear but it brings too many artifacts with PRMan
                    # type="cubic",  # Tried linear but it brings too many artifacts with PRMan
                    basis_id=each % len(bezier_types),
                    width_interpolation_id=each % len(widths_interpolation_types),
                    max_width=1-(each/depth)
                )
                # Set normals only here to create "ribbons"
                with Sdf.ChangeBlock():
                    normal_interpolation_idx = each % len(normal_interpolation_types)
                    normal_interpolation_name = normal_interpolation_types[normal_interpolation_idx].interpolation()
                    normal_interpolation_size = normal_interpolation_types[normal_interpolation_idx].size(curve)
                    normals_attr = curve.GetNormalsAttr()
                    curve.SetNormalsInterpolation(normal_interpolation_name)
                    curve.GetDoubleSidedAttr().Set(True)
                    normals_attr.Set([(-1, -0.3, 0.3) for _ in range(normal_interpolation_size)])

            for each, curve in enumerate(right_curve_lineup.GetChildren()):
                curve = UsdGeom.BasisCurves(curve)
                set_curve_attrs(
                    curve,
                    type="cubic" if each % 2 else "linear",
                    # type="cubic",  # Tried linear but it brings too many artifacts with PRMan
                    basis_id=(each + 1) % len(bezier_types),
                    width_interpolation_id=(each + 2) % len(widths_interpolation_types),
                    max_width=each / depth
                )
                # Don't set normals only here to create "tubes"

            ground = UsdGeom.Mesh(cook.spawn_unit(golden_krone, geom_plane, geom_root.GetPath().AppendChild("Ground"), label="Ground"))
            with Sdf.ChangeBlock():
                ground.GetDoubleSidedAttr().Set(True)
                ground.GetPrim().SetDocumentation("Main ground where Golden Krone exists")

            def _define(schema, path, doc):
                geom = schema.Define(stage, geom_root.GetPath().AppendPath(path))
                geom.GetPrim().SetDocumentation(doc)
                return geom
            volume, top_back_left, top_front_left, top_back_right, top_front_right = [
                _define(cls, path, doc) for cls, path, doc in (
                    (UsdGeom.Sphere, "Volume", "Main volume for Golden Krone"),
                    (UsdGeom.Cube, "TopBackLeft", "Golden Krone's top back left section"),
                    (UsdGeom.Capsule, "TopFrontLeft", "Golden Krone's top from left section"),
                    (UsdGeom.Cylinder, "TopBackRight", "Golden Krone's top back right section"),
                    (UsdGeom.Cone, "TopFrontRight", "Golden Krone's top front right section"),
                )
            ]
            # # https://github.com/marcomusy/vedo/issues/86
            # See: https://graphics.pixar.com/usd/docs/Inspecting-and-Authoring-Properties.html
            with Sdf.ChangeBlock():
                volume.GetRadiusAttr().Set(volume_size)
                # TODO: these should be value clips?
                xform = UsdGeom.XformCommonAPI(volume)
                xform.SetTranslate((0, volume_size, 0))
                tilt = 12  # "tilt" on the x-axis
                spin = 1440  # "spin" on the z-axis
                xform.SetRotate((tilt,0,0), time=0)
                # xform.SetRotate((tilt,0,spin), time=192)
                # rotate = xform.GetRotate()
                attr = xform.GetPrim().GetAttribute("xformOp:rotateXYZ")
                _tag_persistent(attr)
                UsdGeom.XformCommonAPI(top_back_right).SetTranslate((volume_size, volume_size * 3, -volume_size))
                UsdGeom.XformCommonAPI(top_front_right).SetTranslate((volume_size, volume_size * 3, volume_size))
                UsdGeom.XformCommonAPI(top_back_left).SetTranslate((-volume_size, volume_size * 3, -volume_size))
                UsdGeom.XformCommonAPI(top_front_left).SetTranslate((-volume_size, volume_size * 3, volume_size))

        wavelength_options = [i for i in gusd._GeomPrimvarInfo if i != gusd._GeomPrimvarInfo.CONSTANT]
        color_options = {
            "constant": (gusd._GeomPrimvarInfo.CONSTANT, _random_colors),
            **{f"random_{i.interpolation()}": (i, _random_colors) for i in wavelength_options},
            **{f"spectrum_{i.interpolation()}": (i, _color_spectrum) for i in wavelength_options},
        }

        golden_color = cook.fetch_stage(golden_asset_name.get(part="Color"))
        # For default color, multiple prims will be using it, so best UX to define the
        # color first, then add it to existing prims rather than the inverse.
        geoms_with_color = [gprim for prim in Usd.PrimRange(geom_root) if (gprim := UsdGeom.Gprim(prim))]

        color_set = golden_krone.GetVariantSets().AddVariantSet("color")

        for option_name, (primvar_meta, color_caller) in color_options.items():
            with Sdf.ChangeBlock():
                color_set.AddVariant(option_name)
                color_set.SetVariantSelection(option_name)
            with Sdf.ChangeBlock(), gusd.edit_context(color_set, cook.unit_asset(golden_krone)):
                golden_color_path = Sdf.Path.absoluteRootPath.AppendPath(option_name)
                golden_color.OverridePrim(golden_color_path)
                arc = Sdf.Reference(cook.asset_identifier(golden_color.GetRootLayer().identifier), golden_color_path)
                golden_krone.GetReferences().AddReference(arc)
                with gusd.edit_context(arc, golden_krone):
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

        # extent = volume.GetExtentAttr()
        # extent.Set(extent.Get() * volume_size)

    romania_asset_name = names.UsdAsset(Usd.ModelAPI(romania).GetAssetIdentifier().path)
    with cook.unit_context(romania):
        romania_geom = cook.fetch_stage(romania_asset_name.get(part="Geom"))
        romania_geom_default_prim = romania_geom.DefinePrim(cook._UNIT_ORIGIN_PATH)
        romania_payload = Sdf.Payload(cook.asset_identifier(romania_geom.GetRootLayer().identifier))
        # with Sdf.ChangeBlock():
        #     romania_geom.SetDefaultPrim(romania_geom_default_prim)
        #     romania.GetPayloads().AddPayload(romania_payload)
        instancer_path = (romania_path:=romania.GetPath()).AppendPath("Buildings")
        targets = []
        # TODO: build another point instancer on another unit, then merge and see what happens
        selections = ("", *color_set.GetVariantNames())
        # selections = ("", "constant")  # DEBUG PURPOSES FOR PIXAR REPORT
        prototypes_paths = [
            instancer_path.AppendPath(
                (name := golden_krone.GetName()) if not selection else f"{name}_{selection}"
            ).MakeRelativePath(romania_path) for selection in selections
        ]
        prototypes = cook.spawn_many(romania, golden_krone, prototypes_paths)
        with Sdf.ChangeBlock():
            romania_geom.SetDefaultPrim(romania_geom_default_prim)
            romania.GetPayloads().AddPayload(romania_payload)
            for prototype, selection in zip(prototypes, selections, strict=True):
                if selection:
                    prototype.GetVariantSet("color").SetVariantSelection(selection)
                relpath = prototype.GetPath().MakeRelativePath(instancer_path)
                targets.append(relpath)

        with gusd.edit_context(romania_payload, romania):
            buildings = UsdGeom.PointInstancer.Define(stage, instancer_path)
            # X_size = 20 # 40
            # Z_size = 15 # 30
            X_size = 10 # 40
            Z_size = 7  # 30
            # X_size = 4 # 40
            # Z_size = 3  # 30
            # Y_size = 10  # 250
            Y_size = Z_size * 7  # 250
            X = np.linspace(0, (X_size*width)-width, X_size)
            Z = np.linspace(0, (Z_size*depth)-depth, Z_size)
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

    with cook.unit_context(budapest):
        budapest.GetAttribute("modern_name").Set('Budapest!')

    instancer_tx = int(5 * X_size)
    instancer_ty = int(1.5 * Y_size)

    for i, top_country in enumerate((inherits_country, specializes_country, unchanged)):
        with cook.unit_context(top_country):
            paths = (
                "Deeper/Nested/Romania1",
                "Deeper/Nested/Romania2",
                "Deeper/Nested/Romania3",
                "Deeper/Nested/Romania4",
            )
            transforms = (
                (-instancer_tx * (i + 1), instancer_ty * (i + 1), 1),
                (instancer_tx * (i + 1), instancer_ty * (i + 1), 1),
                (-instancer_tx * (i + 1), -instancer_ty * (i + 1), 1),
                (instancer_tx * (i + 1), -instancer_ty * (i + 1), 1),
            )
            instances = cook.spawn_many(top_country, romania, paths)

            specializing = bool(i == 0 or i == 1)
            if specializing:
                specialized_prim = instances[0].GetPrimAtPath(prototypes_paths[0])
                edit_method = cook.specialized_context if i == 1 else cook.inherited_context
                broadcast_color = "spectrum_vertex" if i == 1 else "random_vertex"

            with Sdf.ChangeBlock():
                for r_inst, value in zip(instances, transforms, strict=True):
                    UsdGeom.XformCommonAPI(r_inst).SetTranslate(value)
                    # Workflow: if we're going to broadcast changes, don't instance the point instancer.
                    if specializing:
                        with edit_method(specialized_prim, top_country):
                            specialized_prim.GetVariantSet("color").SetVariantSelection(broadcast_color)
                        ########################
                        # Note: when making changes on instances, try to always use variant sets to reduce total prototype count
                        # (using specializes or inhertis create additional localized opinions which increase amount of prototypes)
                        # for child in r_inst.GetPrimAtPath("Buildings").GetChildren():
                        #     print(f"{child=}")
                        #     child.GetVariantSet("color").SetVariantSelection("spectrum_vertex")
                        # ########################
                        # local_stage = Usd.Stage.Open(cook.unit_asset(top_country))
                        # # specializes path to component level can't be mapped via edit target
                        # specialized = local_stage.OverridePrim("/Specialized/Model/Place/GoldenKroneHotel")
                        # specialized.GetVariantSet("color").SetVariantSelection("spectrum_vertex")
                        ####### Uncomment these lines to ensure specialized takes effect in deterministic ways when instancing!!!! ######
                        # local_stage.CreateClassPrim("/__temp")
                        # r_inst.GetReferences().AddInternalReference("/__temp")
                        # # ####### Uncomment these lines to ensure specialized takes effect in deterministic ways when instancing!!!! ######
                        # r_inst.SetInstanceable(True)
                        ...
                    else:
                        ...
                        r_inst.SetInstanceable(True)

    sailors = {
        "TheCaptain": "Captain",
        "Petrofsky": "FirstMate",
        "TheFirstMate": "FirstMate",
        "TheCook": "Cook",
    }
    sailor_prims = cook.create_many(sailor, sailors)
    demeter = cook.create_unit(ship, "TheDemeter")
    demeter_sailors = demeter.GetRelationship("sailors")
    with Sdf.ChangeBlock():
        for sailor_prim, rank in zip(sailor_prims, sailors.values()):
            with cook.unit_context(sailor_prim):
                sailor_prim.GetVariantSet("Rank").SetVariantSelection(rank)
            demeter_sailors.AddTarget(sailor_prim.GetPath())

        """
        If you just want to return a single part of a type without the object structure, you can use . after the type name. For example, SELECT City.modern_name will give this output:
    
        {'Budapest', 'Bistrița'}
        """
        # print([p for p in cook.itaxa(stage.Traverse(), city) if p.GetAttribute("modern_name").Get()])
        # [Usd.Prim(</City/Budapest>), Usd.Prim(</City/Bistritz>)]

        """
        But we want to have Jonathan be connected to the cities he has traveled to. We'll change places_visited when we INSERT to places_visited := City:
        """

        for each, places in (
            (jonathan, [munich, budapest, bistritz, london, romania, castle_dracula]),
            # (emil, cook.itaxa(stage.Traverse(), city)),
            (dracula, [romania]),
            (mina, [castle_dracula, romania]),
            (sailor, [london]),  # can propagate updates to a whole taxon group <- NOT ANYMORE
            (non_player, [london]),  # can propagate updates to a whole taxon group
        ):
            visit_rel = each.GetRelationship('places_visited')
            for place in places:
                visit_rel.AddTarget(place.GetPath())

        with cook.unit_context(emil):
            emil.GetVariantSet("Transport").SetVariantSelection("HorseDrawnCarriage")

    # DELETING
    # try deleting the countries, this works as long as definitions are on the current edit target
    # note how relationships still exist (since they're authored paths)
    # country_root = stage.GetPrimAtPath(f"/{city_type.GetName()}")
    # stage.RemovePrim(country_root.GetPath())

    # 4 Questions / Unresolved
    # Time type, needed? Has "awake" property  driven by hour ( awake < 7am asleep < 19h awake

    # 2023-02-26
    # Total time: 0:00:16.560353

    # 2023-07-29 py310 usd2305
    # Total time: 0:00:10.867913

    # 2023-07-29 py311 usd2308
    # Total time: 0:00:10.884778

    # 2023-11-26 py312 usd2311
    # Total time: 0:00:09.438108

    # 2024-11-03 py312 usd2405
    # Total time: 0:00:08.470964

    # 2024-11-03 py313 usd2411
    # Total time: 0:00:06.371738

    amount = 1
    for taxon in (city, other_place, person):
        cook.create_many(taxon, *zip(*[(f'New{taxon.GetName()}{name}', f'New {taxon.GetName()} Hello {name}') for name in range(amount)]))


    # We know that Jonathan can't break out of the castle, but let's try to show it using a query. To do that, he needs to have a strength greater than that of a door. Or in other words, he needs a greater strength than the weakest door.
    # Fortunately, there is a function called min() that gives the minimum value of a set, so we can use that. If his strength is higher than the door with the smallest number, then he can escape. This query looks like it should work, but not quite:
    if (strength := jonathan.GetAttribute("strength").Get()) > (weakest_door:=min(doors_strength.Get())):
        raise ValueError(f"Did not expect {jonathan} to be able to leave the castle! His {strength=} is greater than {weakest_door=}")

    cook.Repository.reset(token)
    return stage


# import edgedb
import os
# for env_var in ("EDGEDB_INSTANCE", "EDGEDB_SECRET_KEY"):
#     value = os.getenv(env_var)
#     if not value:
#         raise RuntimeError(f"{env_var} not defined in current environment")
#     print(f"{env_var}={value}")


def _types_to_create_query(stage):
    print(f"-->>> Creating types for {stage}")
    root = stage.GetPrimAtPath(cook._TAXONOMY_ROOT_PATH)
    taxa = [prim for prim in root.GetFilteredChildren(Usd.PrimAllPrimsPredicate) if prim.GetAssetInfoByKey(cook._ASSETINFO_TAXON_KEY)]
    graph = cook.taxonomy_graph(taxa, "")
    properties = dict()  # {taxon: {name: type}}
    types_to_commit = dict()
    from collections import ChainMap
    for each in networkx.topological_sort(graph):
        print(each)
        taxon_info = dict()
        name = graph.nodes[each]['label']
        taxon = root.GetPrimAtPath(name)
        print(f"{taxon=}")
        taxon_properties = dict()
        taxon_relationships = dict()
        ancestor_names = [graph.nodes[ancestor]['label'] for ancestor in networkx.ancestors(graph, each)]
        ancestors_properties = ChainMap(*(properties[ancestor] for ancestor in ancestor_names))
        # ancestors_rels = ChainMap(*(properties[ancestor] for ancestor in ancestor_names))
        if ancestor_names:
            taxon_info['extending'] = ancestor_names
        print(f"{ancestors_properties.keys()=}")
        for prop in taxon.GetProperties():
            if not prop.GetAssetInfoByKey("grill:database"):
                continue
            prop_name = prop.GetBaseName()
            if prop_name in ancestors_properties:
                continue
            if isinstance(prop, Usd.Attribute):
                taxon_properties[prop.GetBaseName()] = prop.GetTypeName()
            elif isinstance(prop, Usd.Relationship):
                target = prop.GetAssetInfoByKey("grill:target_taxon")
                taxon_relationships[prop.GetBaseName()] = target
            else:
                raise RuntimeError(f"Don't know how to handle {type(prop)} {prop}")
        taxon_info['properties'] = taxon_properties
        taxon_info['links'] = taxon_relationships
        properties[taxon.GetName()] = ChainMap(taxon_properties, taxon_relationships)
        print(graph[each])
        types_to_commit[taxon.GetName()] = taxon_info
        print(networkx.ancestors(graph, each))
        print('===================')

    db_types = {
        Sdf.ValueTypeNames.Int: 'int16',
        Sdf.ValueTypeNames.String: 'str',
    }
    alter_string = ""
    query_string = ""
    for type_name, type_info in types_to_commit.items():
        extending = type_info.get("extending", [])
        extending = f' extending {", ".join(extending)}' if extending else ''
        statement = f'create type {type_name}{extending}'
        if not extending:
            properties = 'create required property name -> str;\n'
        else:
            properties = ''
        if not set(type_info['properties'].values()).issubset(set(db_types.keys())):
            missing = set(type_info['properties'].values())-set(db_types.items())
            from pprint import pp
            pp([str(tn) for tn in set(type_info['properties'].values())])
            raise RuntimeError(f"Missing: {', '.join(str(x) for x in missing)}")
        properties += '\n'.join(f'create property {name} -> {db_types[type_name]};' for name, type_name in type_info['properties'].items())
        links = '\n'.join(f'create multi link {name} -> {whom};' for name, whom in type_info['links'].items())
        query_string += '''%s {
            %s
        };
        ''' % (statement, properties)
        if type_info['links']:
            alter_statement = f'alter type {type_name}'
            alter_string += '''%s {
            %s
            };
            ''' % (alter_statement, links)
    return query_string, alter_string


def edgedb_commit(query):
    return
    query, alter = query
    print("connecting")
    client = edgedb.create_client()
    client.ensure_connected()
    print("connected")
    print("QUERY")
    print(query)
    if alter:
        print(alter)
    # result = client.query('''
    #     select "Jonathan Harker";
    # ''')
    # print(result)
    # print(result)
    # result = client.execute('''
    #     ALTER TYPE NPC {
    #         DROP LINK cities;
    #     };
    # ''')
    # result = client.execute('''
    #     drop type NPC;
    #     drop type City;
    # ''')
    # create type TypeName {
    #   required title: str;
    #   multi actors: Person;
    # }
    # result = client.execute('''
    #     ALTER TYPE NPC {
    #         CREATE MULTI LINK places_visited -> City;
    #     };
    # ''')
    # result = client.execute('''
    #     CREATE TYPE City {
    #         CREATE REQUIRED PROPERTY name -> str;
    #         CREATE PROPERTY modern_name -> str;
    #     };
    #     CREATE TYPE NPC {
    #         CREATE REQUIRED PROPERTY name -> str;
    #         CREATE MULTI LINK places_visited -> City;
    #     };
    # ''')
    result = client.execute(query)
    print(result)
    if alter:
        result = client.execute(alter)
        print(result)
    client.close()
    print("closed")


if __name__ == "__main__":
    import shutil
    import sys
    source_root = Path(__file__).parent
    build_root = source_root / "assets"
    shutil.rmtree(build_root, True)

    logging.basicConfig(level=logging.DEBUG)
    import cProfile

    start = datetime.datetime.now()
    with cProfile.Profile() as pr:
        stage = main()

    pr.dump_stats(str(Path(__file__).parent / "stats_no_init_name.log"))
    end = datetime.datetime.now()
    print(f"Total time: {end - start}")
    stage.Save()
    # stage = main()

    ### Time to practice ###
    # 1. How would you complete it so that it says "Pleased to meet you, I'm " and then the NPC's name?
    # for each in write._iter_taxa(stage, "NonPlayer", predicate=Usd.PrimAllPrimsPredicate):
    #     print(f"Pleased to meet you, I'm {each.GetName()}")

    # 2. How would you update Mina's `places_visited` to include Romania if she went to Castle Dracula for a visit?
    prims = stage.Traverse()
    # mina = next(cook.itaxa(prims, "NonPlayer"), None)
    # assert mina is not None
    # mina_places = mina.GetRelationship("places_visited")
    # for each in cook.itaxa(prims, "Place"):
    #     if each.GetName() in {"CastleDracula", "Romania"}:
    #         print(f"Adding {each}")
    #         mina_places.AddTarget(each.GetPath())

    # 3. With the set `{'W', 'J', 'C'}`, how would you display all the `Person` types with a name that contains any of these capital letters?
    letters = {'W', 'J', 'C'}
    # from pprint import pprint
    # pprint([i for i in cook.itaxa(prims, 'Person') if letters.intersection(i.GetName())])

    # 5. How would you add ' the Great' to every Person type?
    # from pxr import UsdUI
    # for each in cook.itaxa(prims, 'Person'):
    #     try:
    #         each.SetDisplayName(each.GetName() + ' the Great')
    #     except AttributeError:  # USD-22.8+
    #         pass
        # ui = UsdUI.SceneGraphPrimAPI(each)
        # display_name = ui.GetDisplayNameAttr()
        # display_name.Set(display_name.Get() + ' the Great')

    # WITH cities := City.population
    # SELECT (
    #   'Number of cities: ' ++ <str>count(cities),
    #   'All cities have more than 50,000 people: ' ++ <str>all(cities > 50000),
    #   'Total population: ' ++ <str>sum(cities),
    #   'Smallest and largest population: ' ++ <str>min(cities) ++ ', ' ++ <str>max(cities),
    #   'Average population: ' ++ <str>math::mean(cities),
    #   'At least one city has more than 5 million people: ' ++ <str>any(cities > 5000000),
    #   'Standard deviation: ' ++ <str>math::stddev(cities)
    # );
    # cities = tuple(cook.itaxa(prims, 'City'))
    # print(f"""
    # Number of cities: {len(cities)},
    # All cities have more than 50,000 people: {', '.join(c.GetName() for c in cities if c.GetAttribute('population').Get() or 0 > 50000) },
    # Total population:  {sum(c.GetAttribute('population').Get() or 0 for c in cities)},
    # """)
    print(f"Total notices {next(_notice_counter)}")
    # queries = _types_to_create_query(stage)
    # edgedb_commit(queries)


# TODO:
# delimiters for at symbols
# unicode
# https://github.com/PixarAnimationStudios/OpenUSD/blob/79d80a0f4128a17eaff29ef08c1be3c2fcf0151d/pxr/usd/sdf/testenv/testSdfParsing.testenv/baseline/180_asset_paths.sdf
# https://github.com/PixarAnimationStudios/OpenUSD/blob/79d80a0f4128a17eaff29ef08c1be3c2fcf0151d/pxr/usd/sdf/testenv/testSdfParsing.testenv/baseline/120_sub_attribute_relations.sdf

# https://github.com/PixarAnimationStudios/OpenUSD/blob/79d80a0f4128a17eaff29ef08c1be3c2fcf0151d/pxr/usd/sdf/testenv/testSdfParsing.testenv/baseline/202_displayGroups.sdf
# https://github.com/PixarAnimationStudios/OpenUSD/blob/79d80a0f4128a17eaff29ef08c1be3c2fcf0151d/pxr/usd/sdf/testenv/testSdfParsing.testenv/baseline/217_utf8_identifiers.sdf

# string on string on string
# https://github.com/PixarAnimationStudios/OpenUSD/blob/79d80a0f4128a17eaff29ef08c1be3c2fcf0151d/pxr/usd/sdf/testenv/testSdfParsing.testenv/baseline/31_attribute_values.sdf

# https://github.com/PixarAnimationStudios/OpenUSD/blob/79d80a0f4128a17eaff29ef08c1be3c2fcf0151d/pxr/usd/sdf/testenv/testSdfParsing.testenv/baseline/46_weirdStringContent.sdf

# https://github.com/PixarAnimationStudios/OpenUSD/blob/79d80a0f4128a17eaff29ef08c1be3c2fcf0151d/pxr/usd/sdf/testenv/testSdfParsing.testenv/baseline/88_attribute_displayUnit.sdf