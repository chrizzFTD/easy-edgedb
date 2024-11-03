import logging
import datetime
from pathlib import Path

from pxr import Sdf

from grill import cook, names
from grill.tokens import ids

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

names.UsdAsset.DEFAULT_SUFFIX = "usda"

def main():
    token = cook.Repository.set(Path(__file__).parent / "assets")

    stage = cook.fetch_stage(cook.UsdAsset.get_default(code='dracula'))

    # Define taxonomy
    _object_fields = {ids.CGAsset.kingdom.name: "Object"}
    with cook.taxonomy_context(stage):
        person = cook.define_taxon(stage, "Person", id_fields=_object_fields)
        transport = cook.define_taxon(stage, "Transport", id_fields=_object_fields)
        place = cook.define_taxon(stage, "Place", id_fields=_object_fields)
        player = cook.define_taxon(stage, "Player", references=(person, transport))
        non_player = cook.define_taxon(stage, "NonPlayer", references=(person,))
        vampire = cook.define_taxon(stage, "Vampire", references=(person,))
        minor_vampire = cook.define_taxon(stage, "MinorVampire", references=(person,))
        city = cook.define_taxon(stage, "City", references=(place,))
        country = cook.define_taxon(stage, "Country", references=(place,))

        # Edit taxonomy
        # TODO: how to add constraints? Useful to catch errors before they hit the database
        #   https://github.com/edgedb/easy-edgedb/blob/master/chapter3/index.md#adding-constraints
        person.CreateAttribute('age', Sdf.ValueTypeNames.Int2, custom=False)
        place.CreateAttribute("modern_name", Sdf.ValueTypeNames.String, custom=False)

        person.CreateRelationship('lover', custom=False)
        person.CreateRelationship('places_visited', custom=False)
        minor_vampire.CreateRelationship('master', custom=False)  # it needs to be a vampire

        variant_set = transport.GetVariantSets().AddVariantSet("Transport")
        for set_name in ("Feet", "Train", "HorseDrawnCarriage"):
            variant_set.AddVariant(set_name)


    cook.create_unit(city, 'Munich')
    budapest = cook.create_unit(city, 'Budapest', label='Buda-Pesth')
    bistritz = cook.create_unit(city, 'Bistritz', label='Bistritz')
    london = cook.create_unit(city, 'London')
    golden_krone = cook.create_unit(place, 'GoldenKroneHotel', label='Golden Krone Hotel')
    cook.create_unit(country, 'Hungary')
    romania = cook.create_unit(country, 'Romania')

    jonathan = cook.create_unit(person, 'JonathanHarker', label='Jonathan Harker')
    emil = cook.create_unit(player, "EmilSinclair", label="Emil Sinclair")
    dracula = cook.create_unit(vampire, 'CountDracula', label='Count Dracula')
    woman1 = cook.create_unit(minor_vampire, 'Woman01', label='Woman 1')
    woman1.GetRelationship("master").AddTarget(dracula.GetPath())
    mina = cook.create_unit(non_player, 'MinaMurray', label='Mina Murray')
    mina.GetRelationship("lover").AddTarget(jonathan.GetPath())

    with cook.unit_context(bistritz):
        bistritz.GetAttribute("modern_name").Set('Bistrița')
        # we could set "important_places" as a custom new property
        # but "important" prims are already provided by the USD model hierarchy.
        cook.spawn_unit(bistritz, golden_krone)

    with cook.unit_context(budapest):
        budapest.GetAttribute("modern_name").Set('Budapest!')

    """
    If you just want to return a single part of a type without the object structure, you can use . after the type name. For example, SELECT City.modern_name will give this output:

    {'Budapest', 'Bistrița'}
    """
    print([p for p in cook.itaxa(stage.Traverse(), city) if p.GetAttribute("modern_name").Get()])
    # [Usd.Prim(</City/Budapest>), Usd.Prim(</City/Bistritz>)]

    """
    But we want to have Jonathan be connected to the cities he has traveled to. We'll change places_visited when we INSERT to places_visited := City:
    """
    for person, places in {
        jonathan: cook.itaxa(stage.Traverse(), city),
        emil: cook.itaxa(stage.Traverse(), city),
        dracula: [romania],
        mina: [london],
    }.items():
        visit_rel = person.GetRelationship('places_visited')
        for each in places:
            visit_rel.AddTarget(each.GetPath())

    with cook.unit_context(emil):
        emil.GetVariantSet("Transport").SetVariantSelection("HorseDrawnCarriage")

    # DELETING
    # try deleting the countries, this works as long as definitions are on the current edit target
    # note how relationships still exist (since they're authored paths)
    # country_root = stage.GetPrimAtPath(f"/{city_type.GetName()}")
    # stage.RemovePrim(country_root.GetPath())

    # 4 Questions / Unresolved
    # Time type, needed? Has "awake" property  driven by hour ( awake < 7am asleep < 19h awake

    # # for x in range(1_000):
    # for x in range(10):
    #     # atm creating 1_000 new cities (including each USD file) takes around 7 seconds.
    #     # Total time: 0:00:06.993190
    #     # could be faster.
    #     cook.create_unit(city, f'NewCity{x}', label=f"New City Hello {x}")

    stage.Save()
    cook.Repository.reset(token)
    return stage


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    import cProfile
    start = datetime.datetime.now()
    with cProfile.Profile() as pr:
        stage = main()

    pr.dump_stats(str(Path(__file__).parent / "stats_no_init_name.log"))

    end = datetime.datetime.now()
    print(f"Total time: {end - start}")
