import logging
import datetime
import colorsys
from pathlib import Path

import numpy as np
from pxr import Sdf, UsdGeom

from grill import cook
from grill.tokens import ids

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    token = cook.Repository.set(Path(__file__).parent / "assets")
    stage = cook.fetch_stage(cook.UsdAsset.get_default(code='dracula'))

    # 1. Taxonomy Definition
    # 1.1 Object kingdom is for "all things that exist" in the universe.
    _object_fields = {ids.CGAsset.kingdom.name: "Object"}
    with cook.taxonomy_context(stage):
        # 1.2 These are the "foundational" objects that other taxa inherit from.
        person, transport, place, ship = [
            cook.define_taxon(stage, name, id_fields=_object_fields)
            for name in ("Person", "LandTransport", "Place", "Ship",)
        ]
        for each in (person, place, ship):  # base xformable taxa
            UsdGeom.Xform.Define(stage, each.GetPath())

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
    golden_krone = cook.create(place, 'GoldenKroneHotel', label='Golden Krone Hotel')
    castle_dracula = cook.create(other_place, 'CastleDracula', label='Castle Dracula')
    # 2.1 Create attributes as needed
    with cook.unit_context(castle_dracula):
        doors_strength = castle_dracula.CreateAttribute('doors_strength', Sdf.ValueTypeNames.IntArray, custom=False)
        doors_strength.Set([6, 19, 10])

    romania, hungary, *__ = cook.create_many(country, ('Romania', 'Hungary', 'France', 'Slovakia'))

    jonathan = cook.create(person, 'JonathanHarker', label='Jonathan Harker')
    with cook.unit_context(jonathan):
        jonathan.GetAttribute("strength").Set(5)

    emil = cook.create(player, "EmilSinclair", label="Emil Sinclair")
    dracula = cook.create(vampire, 'CountDracula', label='Count Dracula')
    for each in cook.create_many(minor_vampire, *zip(*[(f'Woman{i}', f'Woman {i}') for i in range(4)])):
        dracula.GetRelationship("slaves").AddTarget(each.GetPath())

    mina = cook.create(non_player, 'MinaMurray', label='Mina Murray')
    lucy = cook.create(non_player, 'LucyWestenra', label='Lucy Westenra')
    arthur, renfield, *__ = cook.create_many(non_player, ('ArthurHolmwood', 'Renfield', 'JohnSeward', 'QuinceyMorris'))
    arthur.GetRelationship('lover').AddTarget(lucy.GetPath())
    lucy.GetRelationship("lover").AddTarget(arthur.GetPath())

    renfield.GetAttribute("strength").Set(10)

    mina.GetRelationship("lover").AddTarget(jonathan.GetPath())
    jonathan.GetRelationship("lover").AddTarget(mina.GetPath())
    with cook.unit_context(bistritz):
        bistritz.GetAttribute("modern_name").Set('Bistrița')
        for path, value in (
                ("", (2, 4, 6)),
                ("Deeper/Nested/Golden1", (-4, 2, 1)),
                ("Deeper/Nested/Golden2", (-4, -2, 1)),
                ("Deeper/Nested/Golden3", (0, 4, -2)),
        ):
            spawned = UsdGeom.Xform(cook.spawn_unit(bistritz, golden_krone, path))
            spawned.AddTranslateOp().Set(value=value)

    stage.SetStartTimeCode(0)
    stage.SetEndTimeCode(192)

    with cook.unit_context(golden_krone):
        # See: https://graphics.pixar.com/usd/docs/Inspecting-and-Authoring-Properties.html
        volume_path = "GEOM/volume"
        volume = UsdGeom.Sphere.Define(stage, golden_krone.GetPath().AppendPath(volume_path))
        size = 2
        # TODO: This must be a payload
        color_options = dict(
            random=(UsdGeom.Tokens.vertex, primvar_size := 92, np.random.dirichlet(np.ones(3), size=primvar_size)),
            spectrum_smooth=(UsdGeom.Tokens.vertex, primvar_size := 92, [colorsys.hsv_to_rgb(x/primvar_size, 1, .75) for x in range(primvar_size)]),
            spectrum_hard=(UsdGeom.Tokens.faceVarying, primvar_size := 380, [colorsys.hsv_to_rgb(x/primvar_size, 1, .75) for x in range(primvar_size)]),
        )
        from pxr import Usd
        golden_stage = cook.fetch_stage(Usd.ModelAPI(golden_krone).GetAssetIdentifier().path)
        # with color_set.GetVariantEditContext():
        # pxr.Tf.ErrorException:
        # 	Error in 'pxrInternal_v0_21__pxrReserved__::UsdVariantSet::GetVariantEditTarget' at line 181 in file B:\write\code\git\USD\pxr\usd\usd\variantSets.cpp : 'Layer dracula-3d-Object-Place-rnd-main-GoldenKroneHotel-lead-base-whole.1.usda is not a local layer of stage rooted at layer dracula-3d-abc-entity-rnd-main-atom-lead-base-whole.1.usda'
        sets = golden_stage.GetDefaultPrim().GetVariantSets()
        golden_volume = UsdGeom.Sphere(golden_stage.GetDefaultPrim().GetPrimAtPath(volume_path))
        color_set = sets.AddVariantSet("color")
        for option_name, (interpolation, color_size, colors) in color_options.items():
            color_set.AddVariant(option_name)
            color_set.SetVariantSelection(option_name)
            with color_set.GetVariantEditContext():
                color_var = golden_volume.GetDisplayColorPrimvar()
                color_var.SetInterpolation(interpolation)
                color_var.SetElementSize(color_size)
                color_var.Set(colors)
            color_set.ClearVariantSelection()

        volume.GetRadiusAttr().Set(size)

        extent = volume.GetExtentAttr()
        extent.Set(extent.Get() * size)

        spin = volume.AddRotateZOp(opSuffix='spin')
        spin.Set(time=0, value=0)
        spin.Set(time=192, value=1440)
        tilt = volume.AddRotateXOp(opSuffix='tilt')
        tilt.Set(value=12)

        volume.GetPrim().SetDocumentation("This is the main volume for the Golden Krone")

    cook.spawn_unit(romania, hungary)
    cook.spawn_unit(romania, castle_dracula)

    with cook.unit_context(budapest):
        budapest.GetAttribute("modern_name").Set('Budapest!')

    for name, rank in (
        ("TheCaptain", "Captain"),
        ("Petrofsky", "FirstMate"),
        ("TheFirstMate", "FirstMate"),
        ("TheCook", "Cook"),
    ):
        sailor_prim = cook.create(sailor, name)
        with cook.unit_context(sailor_prim):
            sailor_prim.GetVariantSet("Rank").SetVariantSelection(rank)
    demeter = cook.create(ship, "TheDemeter")
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
    # list(write._iter_taxa(stage, place))

    for each, places in {
        # jonathan: city_root.GetChildren(),
        jonathan: [munich, budapest, bistritz, london, romania, castle_dracula],
        emil: cook.itaxa(stage.Traverse(), city),
        dracula: [romania],
        mina: [castle_dracula, romania],
        sailor: [london],  # can propagate updates to a whole taxon group
        non_player: [london],  # can propagate updates to a whole taxon group
    }.items():
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
    # #     write.create(city, f'NewCity{x}', label=f"New City Hello {x}")
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
    # # write.create(city, f'NewNoContext01', label=f'NewNoContext01')
    # # write.create(city, f'NewNoContext02', label=f'NewNoContext02')
    # # new_stage = write.fetch_stage(write.UsdAsset.get_anonymous())
    # # try:
    # #     with write.creation_context(new_stage):
    # #         write.create(city, "Should fail")
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
    #                 write.create(taxon, f'New{taxon.GetName()}{name}', label=f'New {taxon.GetName()} Hello {name}')
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
    #             write.create(taxon, f'New{taxon.GetName()}{name}', label=f'New {taxon.GetName()} Hello {name}')
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
    #     write.create(city, f'NewCity{x}', label=f"New City Hello {x}")
    amount = 2  # TODO: this kills the layerstack description widget ): update to be prim selection based + filter specific?

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
    #         write.create(taxon, f'New{taxon.GetName()}{name}', label=f'New {taxon.GetName()} Hello {name}')

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
    for taxon in (city, other_place, person):
        cook.create_many(taxon, *zip(*[(f'New{taxon.GetName()}{name}', f'New {taxon.GetName()} Hello {name}') for name in range(amount)]))


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
    # pprint([i for i in write._iter_taxa(stage, 'Person') if letters.intersection(each.GetName())])

    # 5. How would you add ' the Great' to every Person type?
    for each in cook.itaxa(prims, 'Person'):
        print(each)
        label = each.GetAttribute('label')
        label.Set(label.Get() or "" + ' the Great')
        # print(label.Get())
