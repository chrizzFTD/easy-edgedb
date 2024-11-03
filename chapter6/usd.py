import logging
import datetime
from pathlib import Path

from pxr import Usd, Sdf, Kind

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
        other_place = cook.define_taxon(stage, "OtherPlace", references=(place,))

        # Edit taxonomy
        # TODO: what should person and place be? Assemblies vs components.
        #       For now, only cities are considered assemblies.
        # all places that end up in the database are "important places"
        for each in (city, country):
            # all places that end up in the database are "important places"
            Usd.ModelAPI(each).SetKind(Kind.Tokens.assembly)

        # TODO: how to add constraints? Useful to catch errors before they hit the database
        #   https://github.com/edgedb/easy-edgedb/blob/master/chapter3/index.md#adding-constraints
        person.CreateAttribute('age', Sdf.ValueTypeNames.Int2, custom=False)
        place.CreateAttribute("modern_name", Sdf.ValueTypeNames.String, custom=False)

        person.CreateRelationship('lover', custom=False)
        person.CreateRelationship('places_visited', custom=False)
        vampire.CreateRelationship('slaves', custom=False)  # it needs to be a vampire

        variant_set = transport.GetVariantSets().AddVariantSet("Transport")
        for set_name in ("Feet", "Train", "HorseDrawnCarriage"):
            variant_set.AddVariant(set_name)


    munich = cook.create_unit(city, 'Munich')
    budapest = cook.create_unit(city, 'Budapest', label='Buda-Pesth')
    bistritz = cook.create_unit(city, 'Bistritz', label='Bistritz')
    london = cook.create_unit(city, 'London')
    golden_krone = cook.create_unit(place, 'GoldenKroneHotel', label='Golden Krone Hotel')
    castle_dracula = cook.create_unit(other_place, 'CastleDracula', label='Castle Dracula')
    cook.create_unit(country, 'Hungary')
    cook.create_unit(country, 'France')
    cook.create_unit(country, 'Slovakia')

    romania = cook.create_unit(country, 'Romania')

    jonathan = cook.create_unit(person, 'JonathanHarker', label='Jonathan Harker')
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

    ### Time to practice ###
    # 1. How would you complete it so that it says "Pleased to meet you, I'm " and then the NPC's name?
    for each in cook.itaxa(stage.Traverse(), "NonPlayer"):
        print(f"Pleased to meet you, I'm {each.GetName()}")

    # 2. How would you update Mina's `places_visited` to include Romania if she went to Castle Dracula for a visit?
    mina = next(cook.itaxa(stage.Traverse(), "NonPlayer"), None)
    assert mina is not None
    from pprint import pprint
    mina_places = mina.GetRelationship("places_visited")
    for each in cook.itaxa(stage.Traverse(), "Place"):
        if each.GetName() in {"CastleDracula", "Romania"}:
            print(f"Adding {each}")
            mina_places.AddTarget(each.GetPath())

    # 3. With the set `{'W', 'J', 'C'}`, how would you display all the `Person` types with a name that contains any of these capital letters?
    letters = {'W', 'J', 'C'}
    pprint([i for i in cook.itaxa(stage.Traverse(), 'Person') if letters.intersection(each.GetName())])

    # 5. How would you add ' the Great' to every Person type?
    from pxr import UsdUI
    for each in cook.itaxa(stage.Traverse(), 'Person'):
        try:
            each.SetDisplayName(each.GetName() + ' the Great')
            print(each.GetDisplayName())
        except AttributeError:  # USD-22.8+
            pass

