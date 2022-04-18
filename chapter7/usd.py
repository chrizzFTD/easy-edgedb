import logging
import datetime
from pathlib import Path

from pxr import Usd, Sdf, Kind

from grill import cook
from grill.tokens import ids

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    token = cook.Repository.set(Path(__file__).parent / "assets")

    stage = cook.fetch_stage(cook.UsdAsset.get_default(code='dracula'))

    # Define taxonomy
    _object_fields = {ids.CGAsset.kingdom.name: "Object"}
    with cook.taxonomy_context(stage):
        person = cook.define_taxon(stage, "Person", id_fields=_object_fields)
        transport = cook.define_taxon(stage, "Transport", id_fields=_object_fields)
        place = cook.define_taxon(stage, "Place", id_fields=_object_fields)
        ship = cook.define_taxon(stage, "Ship", id_fields=_object_fields)

        player = cook.define_taxon(stage, "Player", references=(person, transport))
        non_player = cook.define_taxon(stage, "NonPlayer", references=(person,))
        vampire = cook.define_taxon(stage, "Vampire", references=(person,))
        minor_vampire = cook.define_taxon(stage, "MinorVampire", references=(person,))
        cook.define_taxon(stage, "Crewman", references=(person,))
        sailor = cook.define_taxon(stage, "Sailor", references=(person,))
        city = cook.define_taxon(stage, "City", references=(place,))
        city.CreateAttribute('population', Sdf.ValueTypeNames.Int, custom=False)
        country = cook.define_taxon(stage, "Country", references=(place,))
        other_place = cook.define_taxon(stage, "OtherPlace", references=(place,))

        # Edit taxonomy
        # TODO: how to add constraints? Useful to catch errors before they hit the database
        #   https://github.com/edgedb/easy-edgedb/blob/master/chapter3/index.md#adding-constraints
        age = person.CreateAttribute('age', Sdf.ValueTypeNames.Int, custom=False)
        age.SetDocumentation("This value must be constrained at the data base / application level since USD does not provide easy constraint mechanisms for values yet.")
        strength = person.CreateAttribute('strength', Sdf.ValueTypeNames.Int, custom=False)
        strength.SetDocumentation("Used to help answer if a person is able to perform some actions (e.g. can this person open a door?)")
        place.CreateAttribute("modern_name", Sdf.ValueTypeNames.String, custom=False)

        person.CreateRelationship('lover', custom=False)
        person.CreateRelationship('places_visited', custom=False)
        vampire.CreateRelationship('slaves', custom=False)  # it needs to be a vampire
        ship.CreateRelationship('sailors', custom=False)  # it needs to be a Sailor
        ship.CreateRelationship('crew', custom=False)  # it needs to be a Crewman

        variant_set = transport.GetVariantSets().AddVariantSet("Transport")
        for set_name in ("Feet", "Train", "HorseDrawnCarriage"):
            variant_set.AddVariant(set_name)

        # rank is its own separate type in easyedb, but for now we can keep in under sailor unless something else needs to arc from it
        rank = sailor.GetVariantSets().AddVariantSet("Rank")
        for rank_variant in ("Captain", "FirstMate", "SecondMate", "Cook"):
            rank.AddVariant(rank_variant)

    munich = cook.create_unit(city, 'Munich')
    budapest = cook.create_unit(city, 'Budapest', label='Buda-Pesth')
    bistritz = cook.create_unit(city, 'Bistritz', label='Bistritz')
    london = cook.create_unit(city, 'London')
    golden_krone = cook.create_unit(place, 'GoldenKroneHotel', label='Golden Krone Hotel')
    castle_dracula = cook.create_unit(other_place, 'CastleDracula', label='Castle Dracula')
    with cook.unit_context(castle_dracula):
        doors_strength = castle_dracula.CreateAttribute('doors_strength', Sdf.ValueTypeNames.IntArray, custom=False)
        doors_strength.Set([6, 19, 10])

    for city_name in 'Hungary', 'France', 'Slovakia':
        cook.create_unit(city, city_name)

    romania = cook.create_unit(country, 'Romania')

    jonathan = cook.create_unit(person, 'JonathanHarker', label='Jonathan Harker')
    with cook.unit_context(jonathan):
        jonathan.GetAttribute("strength").Set(5)

    emil = cook.create_unit(player, "EmilSinclair", label="Emil Sinclair")
    dracula = cook.create_unit(vampire, 'CountDracula', label='Count Dracula')
    woman1 = cook.create_unit(minor_vampire, 'Woman01', label='Woman 1')
    woman2 = cook.create_unit(minor_vampire, 'Woman02', label='Woman 2')
    woman3 = cook.create_unit(minor_vampire, 'Woman03', label='Woman 3')
    for each in woman1, woman2, woman3:
        dracula.GetRelationship("slaves").AddTarget(each.GetPath())
    mina = cook.create_unit(non_player, 'MinaMurray', label='Mina Murray')
    mina.GetRelationship("lover").AddTarget(jonathan.GetPath())
    jonathan.GetRelationship("lover").AddTarget(mina.GetPath())

    with cook.unit_context(bistritz):
        bistritz.GetAttribute("modern_name").Set('Bistrița')
        # we could set "important_places" as a custom new property
        # but "important" prims are already provided by the USD model hierarchy.
        cook.spawn_unit(bistritz, golden_krone)

    cook.spawn_unit(romania, castle_dracula)

    with cook.unit_context(budapest):
        budapest.GetAttribute("modern_name").Set('Budapest!')

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
    # list(cook._iter_taxa(stage, place))

    for each, places in {
        # jonathan: city_root.GetChildren(),
        jonathan: [munich, budapest, bistritz, london, romania, castle_dracula],
        emil: cook.itaxa(stage.Traverse(), city),
        dracula: [romania],
        mina: [london],
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
    #     return cook.create_unit_many(city, (f'NewCity{x}' for x in range(amnt)), (f'New City Hello {x}' for x in range(amnt)))

    # # def create_many(amnt):
    # # amount = 2_500
    # amount = 800
    # # amount = 1_000
    # # for x in range(amount):
    # #     # atm creating 1_000 new cities (including each USD file) takes around 7 seconds.
    # #     # Total time: 0:00:06.993190
    # #     # could be faster.
    # #     cook.create_unit(city, f'NewCity{x}', label=f"New City Hello {x}")
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
    # # cook.create_unit_many(city, (f'NewCity{x}' for x in range(amount)), (f'New City Hello {x}' for x in range(int(amount / 2))))
    #
    # # cook.create_unit(city, f'NewNoContext01', label=f'NewNoContext01')
    # # cook.create_unit(city, f'NewNoContext02', label=f'NewNoContext02')
    # # new_stage = cook.fetch_stage(cook.UsdAsset.get_anonymous())
    # # try:
    # #     with cook.creation_context(new_stage):
    # #         cook.create_unit(city, "Should fail")
    # # except cook.CreationContextError:
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
    #     with cook._creation_context(stage):
    #         for name in range(amount):
    #             for taxon in (city, other_place, person):
    #                 cook.create_unit(taxon, f'New{taxon.GetName()}{name}', label=f'New {taxon.GetName()} Hello {name}')
    #
    #
    # def _create_many():
    #     # Total time: 0:00:23.241446
    #     # Total time: 0:00:23.575986
    #     # Total time: 0:00:23.902217
    #     # Total time: 0:00:23.480186
    #     # Total time: 0:00:23.169220
    #     for taxon in (city, other_place, person):
    #         cook.create_unit_many(taxon, (f'New{taxon.GetName()}{name}' for name in range(amount)), (f'New {taxon.GetName()} Hello {name}' for name in range(amount)))

    # def _create_current_main():
    #     # amount = 2_500
    #     # Total time: 0:00:26.855546
    #     # Total time: 0:00:26.656233
    #     # Total time: 0:00:26.886336
    #     # Total time: 0:00:26.358893
    #     # Total time: 0:00:26.282877
    #     for name in range(amount):
    #         for taxon in (city, other_place, person):
    #             cook.create_unit(taxon, f'New{taxon.GetName()}{name}', label=f'New {taxon.GetName()} Hello {name}')
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
    #             cook.create_unitNEW(taxon, f'New{taxon.GetName()}{name}', label=f'New {taxon.GetName()} Hello {name}')

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
    # # pr.runcall(cook.create_unit_many, city, (f'NewCity{x}' for x in range(amount)), (f'New City Hello {x}' for x in range(int(amount / 2))))
    # pr.disable()
    # # pr.dump_stats(str(Path(__file__).parent / "stats_create_with_ctx.log"))
    # pr.dump_stats(str(Path(__file__).parent / "stats_create_many_2108.log"))
    # end = datetime.datetime.now()
    # print(f"Total time: {end - start}")
    # amount = 1_000
    # cook.create_unit_many(city, (f'NewCity{x}' for x in range(amount)), (f'New City Hello {x}' for x in range(int(amount / 2))))
    # for x in range(amount):
    #     # atm creating 1_000 new cities (including each USD file) takes around 7 seconds.
    #     # Total time: 0:00:06.993190
    #     # 0:00:07.193135
    #     # could be faster.
    #     cook.create_unit(city, f'NewCity{x}', label=f"New City Hello {x}")
    amount = 5  # TODO: this kills the layerstack description widget ): update to be prim selection based + filter specific?

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
    for name in range(amount):
        for taxon in (city, other_place, person):
            cook.create_unit(taxon, f'New{taxon.GetName()}{name}', label=f'New {taxon.GetName()} Hello {name}')

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
    #     cook.create_unit_many(taxon, (f'New{taxon.GetName()}{name}' for name in range(amount)), (f'New {taxon.GetName()} Hello {name}' for name in range(amount)))

    # stage.Save()

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
    # for each in cook._iter_taxa(stage, "NonPlayer", predicate=Usd.PrimAllPrimsPredicate):
    #     print(f"Pleased to meet you, I'm {each.GetName()}")

    # 2. How would you update Mina's `places_visited` to include Romania if she went to Castle Dracula for a visit?
    mina = next(cook.itaxa(stage.Traverse(), "NonPlayer"), None)
    assert mina is not None
    # from pprint import pprint
    mina_places = mina.GetRelationship("places_visited")
    for each in cook.itaxa(stage.Traverse(), "Place"):
        if each.GetName() in {"CastleDracula", "Romania"}:
            print(f"Adding {each}")
            mina_places.AddTarget(each.GetPath())

    # 3. With the set `{'W', 'J', 'C'}`, how would you display all the `Person` types with a name that contains any of these capital letters?
    letters = {'W', 'J', 'C'}
    # pprint([i for i in cook.itaxa()(stage, 'Person') if letters.intersection(each.GetName())])

    # 5. How would you add ' the Great' to every Person type?
    from pxr import UsdUI
    for each in cook.itaxa(stage.Traverse(), 'Person'):
        ui = UsdUI.SceneGraphPrimAPI(each)
        display_name = ui.GetDisplayNameAttr()
        display_name.Set(display_name.Get() + ' the Great')
