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


def main():
    token = cook.Repository.set(Path(__file__).parent / "assets")
    stage = cook.fetch_stage(names.UsdAsset.get_default(code='dracula'))

    # 1. Taxonomy Definition
    _shade_fields = {ids.CGAsset.kingdom.name: "Shade"}
    from pxr import Kind
    with cook.taxonomy_context(stage):
        model_default_color = cook.create_unit(
            cook.define_taxon(stage, "Color", id_fields=_shade_fields),
            "ModelDefault"
        )
        with cook.unit_context(model_default_color):
            UsdGeom.Gprim(model_default_color).CreateDisplayColorPrimvar().Set([(0.6, 0.8, 0.9)])
            # TODO: see if component default actually makes sense, for now need to change it
            Usd.ModelAPI(model_default_color).SetKind(Kind.Tokens.subcomponent)

    # 1.1 Object kingdom is for "all things that exist" in the universe.
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

        # 1.3 Add required taxa properties
        city.CreateAttribute('population', Sdf.ValueTypeNames.Int, custom=False)

        # TODO: how to add constraints? Useful to catch errors before they hit the database
        #   https://github.com/edgedb/easy-edgedb/blob/master/chapter3/index.md#adding-constraints
        age = person.CreateAttribute('age', Sdf.ValueTypeNames.Int, custom=False)
        age.SetDocumentation("This value must be constrained at the data base / application level since USD does not provide easy constraint mechanisms for values yet.")
        strength = person.CreateAttribute('strength', Sdf.ValueTypeNames.Int, custom=False)
        strength.SetDocumentation("Used to help answer if a person is able to perform some actions (e.g. can this person open a door?)")

        place.CreateAttribute("modern_name", Sdf.ValueTypeNames.String, custom=False)

        for taxon, relationships in (
            (person, ('lover', 'places_visited')),
            (vampire, ('slaves',)),  # it needs to be a vampire
            (ship, ('sailors', 'crew')),
        ):
            for relationship in relationships:
                taxon.CreateRelationship(relationship, custom=False)

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
        city, ('Budapest', 'Bistritz', 'Munich', 'London'), ('Buda-Pesth', 'Bistritz')
    )
    golden_krone = cook.create_unit(place, 'GoldenKroneHotel', label='Golden Krone Hotel')
    castle_dracula = cook.create_unit(other_place, 'CastleDracula', label='Castle Dracula')
    # 2.1 Create attributes as needed
    with cook.unit_context(castle_dracula):
        doors_strength = castle_dracula.CreateAttribute('doors_strength', Sdf.ValueTypeNames.IntArray, custom=False)
        doors_strength.Set([6, 19, 10])

    romania, hungary, france, *__ = cook.create_many(country, ('Romania', 'Hungary', 'France', 'Slovakia'))

    jonathan = cook.create_unit(person, 'JonathanHarker', label='Jonathan Harker')
    with cook.unit_context(jonathan):
        jonathan.GetAttribute("strength").Set(5)

    emil = cook.create_unit(player, "EmilSinclair", label="Emil Sinclair")
    dracula = cook.create_unit(vampire, 'CountDracula', label='Count Dracula')
    for each in cook.create_many(minor_vampire, *zip(*[(f'Woman{i}', f'Woman {i}') for i in range(4)])):
        dracula.GetRelationship("slaves").AddTarget(each.GetPath())

    mina = cook.create_unit(non_player, 'MinaMurray', label='Mina Murray')
    lucy = cook.create_unit(non_player, 'LucyWestenra', label='Lucy Westenra')
    arthur, renfield, *__ = cook.create_many(non_player, ('ArthurHolmwood', 'Renfield', 'JohnSeward', 'QuinceyMorris'))
    arthur.GetRelationship('lover').AddTarget(lucy.GetPath())
    lucy.GetRelationship("lover").AddTarget(arthur.GetPath())

    with cook.unit_context(renfield):
        renfield.GetAttribute("strength").Set(10)

    mina.GetRelationship("lover").AddTarget(jonathan.GetPath())
    jonathan.GetRelationship("lover").AddTarget(mina.GetPath())
    with cook.unit_context(bistritz):
        bistritz.GetAttribute("modern_name").Set('Bistrița')
        for path, value in (
                ("", (2, 15, 6)),
                ("Deeper/Nested/Golden1", (-4, 5, 1)),
                ("Deeper/Nested/Golden2", (-4, -10, 1)),
                ("Deeper/Nested/Golden3", (0, 10, -2)),
        ):
            spawned = UsdGeom.Xform(cook.spawn_unit(bistritz, golden_krone, path))
            spawned.AddTranslateOp().Set(value=value)

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
        # TODO: let's place payload on the root of the unit
        golden_geom.SetDefaultPrim(golden_geom.DefinePrim(cook._UNIT_ORIGIN_PATH))
        payload = Sdf.Payload(golden_geom.GetRootLayer().identifier)

        # Create a "Geom" prim specializing from the model_default_color, which is a subcomponent unit.
        geom_root = cook.spawn_unit(golden_krone, model_default_color, "Geom")
        geom_root.SetInstanceable(False)  # by default, spawning a unit makes it instanceable.
        geom_root.GetPayloads().AddPayload(payload)

        with gusd.edit_context(payload, geom_root):
            def _define(schema, path, doc):
                geom = schema.Define(stage, geom_root.GetPath().AppendPath(path))
                geom.GetPrim().SetDocumentation(doc)
                return geom

            ground, volume, top_back_left, top_front_left, top_back_right, top_front_right = [
                _define(cls, path, doc) for cls, path, doc in (
                    (UsdGeom.Mesh, "Ground", "Main ground where Golden Krone exists"),
                    (UsdGeom.Sphere, "Volume", "Main volume for Golden Krone"),
                    (UsdGeom.Cube, "TopBackLeft", "Golden Krone's top back left section"),
                    (UsdGeom.Capsule, "TopFrontLeft", "Golden Krone's top from left section"),
                    (UsdGeom.Cylinder, "TopBackRight", "Golden Krone's top back right section"),
                    (UsdGeom.Cone, "TopFrontRight", "Golden Krone's top front right section"),
                )
            ]
            # https://github.com/marcomusy/vedo/issues/86
            # https://blender.stackexchange.com/questions/230534/fastest-way-to-skin-a-grid
            width = 10  # 10
            depth = 8  # 8
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
            ground.GetPointsAttr().Set(points)
            ground.GetFaceVertexCountsAttr().Set(faceVertexCounts)
            ground.GetFaceVertexIndicesAttr().Set(faceVertexIndices)

            volume_size = 2
            # See: https://graphics.pixar.com/usd/docs/Inspecting-and-Authoring-Properties.html
            volume.GetRadiusAttr().Set(volume_size)
            # TODO: these should be value clips?
            volume.AddTranslateOp().Set(value=(0, volume_size, 0))

            spin = volume.AddRotateZOp(opSuffix='spin')
            spin.Set(time=0, value=0)
            spin.Set(time=192, value=1440)
            tilt = volume.AddRotateXOp(opSuffix='tilt')
            tilt.Set(value=12)
            top_back_right.AddTranslateOp().Set(value=(volume_size, volume_size * 3, -volume_size))
            top_front_right.AddTranslateOp().Set(value=(volume_size, volume_size * 3,volume_size))
            top_back_left.AddTranslateOp().Set(value=(-volume_size, volume_size * 3, -volume_size))
            top_front_left.AddTranslateOp().Set(value=(-volume_size, volume_size * 3, volume_size))

        wavelength_options = [i for i in gusd._GeomPrimvarInfo if i != gusd._GeomPrimvarInfo.CONSTANT]
        color_options = {
            "constant": (gusd._GeomPrimvarInfo.CONSTANT, _random_colors),
            **{f"random_{i.interpolation()}": (i, _random_colors) for i in wavelength_options},
            **{f"spectrum_{i.interpolation()}": (i, _color_spectrum) for i in wavelength_options},
        }

        golden_color = cook.fetch_stage(golden_asset_name.get(part="Color"))
        # For default color, multiple prims will be using it, so best UX to define the
        # color first, then add it to existing prims rather than the inverse.
        geoms_with_color = (volume, ground, top_back_left, top_front_left, top_back_right, top_front_right)

        color_set = golden_krone.GetVariantSets().AddVariantSet("color")

        for option_name, (primvar_meta, color_caller) in color_options.items():
            color_set.AddVariant(option_name)
            color_set.SetVariantSelection(option_name)
            with gusd.edit_context(color_set, cook.unit_asset(golden_krone)):
                golden_color_path = Sdf.Path.absoluteRootPath.AppendPath(option_name)
                golden_color.OverridePrim(golden_color_path)
                arc = Sdf.Reference(golden_color.GetRootLayer().identifier, golden_color_path)
                golden_krone.GetReferences().AddReference(arc)
                with gusd.edit_context(arc, golden_krone):
                    interpolation = primvar_meta.interpolation()
                    for geom in geoms_with_color:
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
        romania_geom.SetDefaultPrim(romania_geom.DefinePrim(cook._UNIT_ORIGIN_PATH))
        romania_payload = Sdf.Payload(romania_geom.GetRootLayer().identifier)
        romania.GetPayloads().AddPayload(romania_payload)
        instancer_path = (romania_path:=romania.GetPath()).AppendPath("Buildings")
        targets = []
        # TODO: build another point instancer on another unit, then merge and see what happens
        for selection in ("", *color_set.GetVariantNames()):
            name = golden_krone.GetName()
            if selection:
                name = f"{name}_{selection}"
            # spawn prototypes under point instancer for ease of authoring
            prototype = cook.spawn_unit(romania, golden_krone, path=instancer_path.AppendPath(name).MakeRelativePath(romania_path))
            if selection:
                prototype.GetVariantSet("color").SetVariantSelection(selection)
            relpath = prototype.GetPath().MakeRelativePath(instancer_path)
            targets.append(relpath)
        with gusd.edit_context(romania_payload, romania):
            buildings = UsdGeom.PointInstancer.Define(stage, instancer_path)
            X_size = 20 # 40
            Z_size = 15 # 30
            Y_size = 100 # 250
            X = np.linspace(0, (X_size*width)-width, X_size)
            Z = np.linspace(0, (Z_size*depth)-depth, Z_size)
            Y = np.linspace(0, Y_size, Z_size)
            xx, yy, zz = np.meshgrid(X, Y, Z)
            points = np.stack((xx.ravel(), yy.ravel(), zz.ravel()), axis=1)
            buildings.GetPositionsAttr().Set(points)
            for target in targets:
                buildings.GetPrototypesRel().AddTarget(target)
            proto_size = len(buildings.GetPrototypesRel().GetTargets())
            choices = range(proto_size)
            buildings.GetProtoIndicesAttr().Set(np.random.choice(choices, size=len(points)))

    with cook.unit_context(budapest):
        budapest.GetAttribute("modern_name").Set('Budapest!')

    for i, top_country in enumerate((hungary, france)):
        with cook.unit_context(top_country):
            for path, value in (
                    ("Deeper/Nested/Romania1", (-100*(i+1), 150*(i+1), 1)),
                    ("Deeper/Nested/Romania2", (-100*(i+1), -150*(i+1), 1)),
            ):
                unit = cook.spawn_unit(top_country, romania, path)
                UsdGeom.Xform(unit).AddTranslateOp().Set(value=value)
                unit.SetInstanceable(True)

    for name, rank in (
        ("TheCaptain", "Captain"),
        ("Petrofsky", "FirstMate"),
        ("TheFirstMate", "FirstMate"),
        ("TheCook", "Cook"),
    ):
        sailor_prim = cook.create_unit(sailor, name)
        with cook.unit_context(sailor_prim):
            sailor_prim.GetVariantSet("Rank").SetVariantSelection(rank)
    demeter = cook.create_unit(ship, "TheDemeter")
    demeter_sailors = demeter.GetRelationship("sailors")
    for each in cook.itaxa(stage.Traverse(), sailor):
        demeter_sailors.AddTarget(each.GetPath())

    """
    If you just want to return a single part of a type without the object structure, you can use . after the type name. For example, SELECT City.modern_name will give this output:

    {'Budapest', 'Bistrița'}
    """
    print([p for p in cook.itaxa(stage.Traverse(), city) if p.GetAttribute("modern_name").Get()])
    # [Usd.Prim(</City/Budapest>), Usd.Prim(</City/Bistritz>)]

    """
    But we want to have Jonathan be connected to the cities he has traveled to. We'll change places_visited when we INSERT to places_visited := City:
    """

    for each, places in (
        (jonathan, [munich, budapest, bistritz, london, romania, castle_dracula]),
        (emil, cook.itaxa(stage.Traverse(), city)),
        (dracula, [romania]),
        (mina, [castle_dracula, romania]),
        (sailor, [london]),  # can propagate updates to a whole taxon group
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

    # def create_many(amnt):
    #     return write.create_many(city, (f'NewCity{x}' for x in range(amnt)), (f'New City Hello {x}' for x in range(amnt)))

    # # def create_many(amnt):
    # # amount = 2_500
    # amount = 800
    # # amount = 1_000
    # # for x in range(amount):
    # #     # atm creating 1_000 new cities (including each USD file) takes around 7 seconds.
    # #     # Total time: 0:00:06.993190
    # #     # could be faster.
    # #     write.create_unit(city, f'NewCity{x}', label=f"New City Hello {x}")
    # # amount = 2_500
    # # Total time: 0:00:19.365815
    # # Total time: 0:00:19.604778
    # # Total time: 0:00:19.350577
    # # Total time: 0:00:19.977386
    # # Total time: 0:00:19.436644
    #
    # # amount = 2_500
    # # Total time: 0:00:17.387868
    # # Total time: 0:00:17.346169
    # # Total time: 0:00:17.212084
    # # Total time: 0:00:17.693500
    # # Total time: 0:00:17.092674
    # # write.create_many(city, (f'NewCity{x}' for x in range(amount)), (f'New City Hello {x}' for x in range(int(amount / 2))))
    #
    # # write.create_unit(city, f'NewNoContext01', label=f'NewNoContext01')
    # # write.create_unit(city, f'NewNoContext02', label=f'NewNoContext02')
    # # new_stage = write.fetch_stage(write.UsdAsset.get_anonymous())
    # # try:
    # #     with write.creation_context(new_stage):
    # #         write.create_unit(city, "Should fail")
    # # except write.CreationContextError:
    # #     pass
    #
    # def _create_with_ctx():
    #     # amount = 2_500
    #     # Total time: 0:00:19.009718
    #     # Total time: 0:00:19.031431
    #     # Total time: 0:00:20.025853
    #     # Total time: 0:00:19.449294
    #     # Total time: 0:00:19.336220
    #
    #     # Total time: 0:00:23.978055
    #     # Total time: 0:00:24.118364
    #     # Total time: 0:00:24.191394
    #     # Total time: 0:00:23.803597
    #     # Total time: 0:00:23.744562
    #
    #     # Total time: 0:00:23.581031
    #     # Total time: 0:00:23.948312
    #     # Total time: 0:00:23.947470
    #     # Total time: 0:00:23.478434
    #     # Total time: 0:00:23.536022
    #     with write._creation_context(stage):
    #         for name in range(amount):
    #             for taxon in (city, other_place, person):
    #                 write.create_unit(taxon, f'New{taxon.GetName()}{name}', label=f'New {taxon.GetName()} Hello {name}')
    #
    #
    # def _create_many():
    #     # Total time: 0:00:23.241446
    #     # Total time: 0:00:23.575986
    #     # Total time: 0:00:23.902217
    #     # Total time: 0:00:23.480186
    #     # Total time: 0:00:23.169220
    #     for taxon in (city, other_place, person):
    #         write.create_many(taxon, (f'New{taxon.GetName()}{name}' for name in range(amount)), (f'New {taxon.GetName()} Hello {name}' for name in range(amount)))

    # def _create_current_main():
    #     # amount = 2_500
    #     # Total time: 0:00:26.855546
    #     # Total time: 0:00:26.656233
    #     # Total time: 0:00:26.886336
    #     # Total time: 0:00:26.358893
    #     # Total time: 0:00:26.282877
    #     for name in range(amount):
    #         for taxon in (city, other_place, person):
    #             write.create_unit(taxon, f'New{taxon.GetName()}{name}', label=f'New {taxon.GetName()} Hello {name}')
    #
    #
    # def _create_new_no_ctx():
    #     # amount = 2_500
    #     # Total time: 0:00:26.246826
    #     # Total time: 0:00:25.551721
    #     # Total time: 0:00:25.652539
    #     # Total time: 0:00:25.913648
    #     # Total time: 0:00:26.374476
    #     for name in range(amount):
    #         for taxon in (city, other_place, person):
    #             write.createNEW(taxon, f'New{taxon.GetName()}{name}', label=f'New {taxon.GetName()} Hello {name}')

    # import cProfile
    # start = datetime.datetime.now()
    # pr = cProfile.Profile()
    # pr.enable()
    # # amount = 2_500
    # # amount = 2_500
    # # amount = 1_000
    # # pr.runcall(_create_with_ctx)
    # pr.runcall(_create_many)
    # # # CReating 1_000 new cities takes around 4.5 seconds:
    # # # Total time: 0:00:04.457498
    # # pr.runcall(write.create_many, city, (f'NewCity{x}' for x in range(amount)), (f'New City Hello {x}' for x in range(int(amount / 2))))
    # pr.disable()
    # # pr.dump_stats(str(Path(__file__).parent / "stats_create_with_ctx.log"))
    # pr.dump_stats(str(Path(__file__).parent / "stats_create_many_2108.log"))
    # end = datetime.datetime.now()
    # print(f"Total time: {end - start}")
    # amount = 1_000
    # write.create_many(city, (f'NewCity{x}' for x in range(amount)), (f'New City Hello {x}' for x in range(int(amount / 2))))
    # for x in range(amount):
    #     # atm creating 1_000 new cities (including each USD file) takes around 7 seconds.
    #     # Total time: 0:00:06.993190
    #     # 0:00:07.193135
    #     # could be faster.
    #     write.create_unit(city, f'NewCity{x}', label=f"New City Hello {x}")
    amount = 5
    # 2022 03 24: With the update to include the catalogue on all units, amount = 1_000 (3k units):
    # No sublayered catalogue: Total time: 0:00:21.288368
    # Sublayered catalogue: Total time: 0:02:04.093982
    # Sublayered cataloguee + SdfChangeBlock + No Cache: Total time: 0:00:10.672880

    # amount = 500 (1.5k units):
    # No sublayered catalogue: Total time: 0:00:08.725509
    # Sublayered catalogue: Total time: 0:00:35.310143
    # Sublayered cataloguee + SdfChangeBlock + No Cache: Total time: 0:00:05.617066

    # amount = 250 (750 units):
    # No sublayered catalogue: Total time: 0:00:03.501835
    # Sublayered catalogue: Total time: 0:00:12.058600
    # Sublayered cataloguee + SdfChangeBlock: Total time: 0:00:04.041061

    # amount = 125 (375 units):
    # No sublayered catalogue: Total time: 0:00:01.934740
    # Sublayered catalogue: Total time: 0:00:04.428612


    # Time with 1_000 (3k created assets):
    # create:
    # 0:00:16.194140
    # 0:00:16.295293
    # 0:00:16.271336
    # 0:00:16.103667
    # 0:00:16.274068
    # Total time: 0:00:21.451523
    # Total time: 0:00:20.600851
    # Total time: 0:00:20.353705
    # Total time: 0:00:21.045403
    # Total time: 0:00:20.229527
    # for name in range(amount):
    #     for taxon in (city, other_place, person):
    #         cook.create_unit(taxon, f'New{taxon.GetName()}{name}', label=f'New {taxon.GetName()} Hello {name}')

    # create_many:
    # 0:00:14.795971
    # 0:00:14.118569
    # 0:00:13.850693
    # 0:00:14.003263
    # 0:00:14.163723
    # Total time: 0:00:17.356897
    # Total time: 0:00:16.983126
    # Total time: 0:00:16.548665
    # Total time: 0:00:17.422662
    # Total time: 0:00:16.560353
    # for taxon in (city, other_place, person):
    #     cook.create_many(taxon, *zip(*[(f'New{taxon.GetName()}{name}', f'New {taxon.GetName()} Hello {name}') for name in range(amount)]))


    # We know that Jonathan can't break out of the castle, but let's try to show it using a query. To do that, he needs to have a strength greater than that of a door. Or in other words, he needs a greater strength than the weakest door.
    # Fortunately, there is a function called min() that gives the minimum value of a set, so we can use that. If his strength is higher than the door with the smallest number, then he can escape. This query looks like it should work, but not quite:
    if (strength := jonathan.GetAttribute("strength").Get()) > (weakest_door:=min(doors_strength.Get())):
        raise ValueError(f"Did not expect {jonathan} to be able to leave the castle! His {strength=} is greater than {weakest_door=}")

    cook.Repository.reset(token)
    return stage


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    import cProfile
    start = datetime.datetime.now()
    pr = cProfile.Profile()
    pr.enable()
    stage = pr.runcall(main)
    pr.disable()
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
    mina = next(cook.itaxa(prims, "NonPlayer"), None)
    assert mina is not None
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
    from pxr import UsdUI
    for each in cook.itaxa(prims, 'Person'):
        ui = UsdUI.SceneGraphPrimAPI(each)
        display_name = ui.GetDisplayNameAttr()
        display_name.Set(display_name.Get() + ' the Great')

