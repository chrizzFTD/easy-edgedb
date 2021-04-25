import logging
from pathlib import Path

from pxr import Usd, Sdf, Kind

from grill import write

import datetime


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    token = write.repo.set(Path(__file__).parent / "assets")

    stage = write.fetch_stage(write.UsdAsset.get_default(code='dracula'))

    # we can define a category with or without an edit context
    displayable = write.define_category(stage, "DisplayableName")

    with write.category_context(stage):
        # but to edit a category definition we must be in the proper context
        transport = write.define_category(stage, "Transport")
        person = write.define_category(stage, "Person", references=(displayable,))
        vampire = write.define_category(stage, "Vampire", (person,))
        player = write.define_category(stage, "Player", references=(person, transport))
        non_player = write.define_category(stage, "NonPlayer", references=(person,))
        place = write.define_category(stage, "Place", references=(displayable,))
        city = write.define_category(stage, "City", references=(place,))
        country = write.define_category(stage, "Country", (place,))
        # TODO: what should person and place be? Assemblies vs components.
        #       For now, only cities are considered assemblies.
        # all places that end up in the database are "important places"
        for each in (city, country):
            # all places that end up in the database are "important places"
            Usd.ModelAPI(each).SetKind(Kind.Tokens.assembly)

        # TODO: how to add constraints? Useful to catch errors before they hit the database
        #   https://github.com/edgedb/easy-edgedb/blob/master/chapter3/index.md#adding-constraints
        person.CreateAttribute('age', Sdf.ValueTypeNames.Int2)
        displayable.CreateAttribute("display_name", Sdf.ValueTypeNames.String)
        place.CreateAttribute("modern_name", Sdf.ValueTypeNames.String)

        person.CreateRelationship('lover')
        person.CreateRelationship('places_visited')

        variant_set = transport.GetVariantSets().AddVariantSet("Transport")
        for set_name in ("Feet", "Train", "HorseDrawnCarriage"):
            variant_set.AddVariant(set_name)


    write.create(city, 'Munich')
    budapest = write.create(city, 'Budapest', display_name='Buda-Pesth')
    bistritz = write.create(city, 'Bistritz', display_name='Bistritz')
    london = write.create(city, 'London')
    write.create(country, 'Hungary')
    romania = write.create(country, 'Romania')

    jonathan = write.create(person, 'JonathanHarker', display_name='Jonathan Harker')
    emil = write.create(player, "EmilSinclair", display_name="Emil Sinclair")
    dracula = write.create(vampire, 'CountDracula', display_name='Count Dracula')
    mina = write.create(non_player, 'MinaMurray', display_name='Mina Murray')
    mina.GetRelationship("lover").AddTarget(jonathan.GetPath())

    with write.asset_context(bistritz):
        bistritz.GetAttribute("modern_name").Set('Bistrița')

    with write.asset_context(budapest):
        budapest.GetAttribute("modern_name").Set('Budapest!')

    city_root = stage.GetPseudoRoot().GetPrimAtPath(city.GetName())

    """
    If you just want to return a single part of a type without the object structure, you can use . after the type name. For example, SELECT City.modern_name will give this output:

    {'Budapest', 'Bistrița'}
    """
    print([p for p in Usd.PrimRange(city_root) if p.GetAttribute("modern_name").Get()])
    # [Usd.Prim(</City/Budapest>), Usd.Prim(</City/Bistritz>)]

    """
    But we want to have Jonathan be connected to the cities he has traveled to. We'll change places_visited when we INSERT to places_visited := City:
    """
    for person, places in {
        jonathan: city_root.GetChildren(),
        emil: city_root.GetChildren(),
        dracula: [romania],
        mina: [london],
    }.items():
        visit_rel = person.GetRelationship('places_visited')
        for each in places:
            visit_rel.AddTarget(each.GetPath())

    # we could set "important_places" as a custom new property
    # but "important" prims are already provided by the USD model hierarchy.
    # let's try it and see if we can get away with it.
    goldenKrone = write.create(place, 'GoldenKroneHotel', display_name='Golden Krone Hotel')
    # also, let's make it a child of bistritz
    child_prim = stage.OverridePrim(bistritz.GetPath().AppendChild(goldenKrone.GetName()))
    child_prim.GetReferences().AddInternalReference(goldenKrone.GetPath())
    Usd.ModelAPI(child_prim).SetKind(Kind.Tokens.component)  # should be component or reference?

    with write.asset_context(emil):
        emil.GetVariantSet("Transport").SetVariantSelection("HorseDrawnCarriage")

    # DELETING
    # try deleting the countries, this works as long as definitions are on the current edit target
    # note how relationships still exist (since they're authored paths)
    # country_root = stage.GetPrimAtPath(f"/{city_type.GetName()}")
    # stage.RemovePrim(country_root.GetPath())

    # 4 Questions / Unresolved
    # Time type, needed? Has "awake" property  driven by hour ( awake < 7am asleep < 19h awake

    for x in range(5):
        # atm creating 1_000 new cities (including each USD file) takes around 7 seconds.
        # could be faster.
        write.create(city, f'NewCity{x}', display_name=f"New City Hello {x}")

    stage.Save()
    write.repo.reset(token)


if __name__ == "__main__":
    # tos()
    logging.basicConfig(level=logging.DEBUG)
    # logging.getLogger("grill").setLevel(logging.DEBUG)
    import cProfile
    start = datetime.datetime.now()
    pr = cProfile.Profile()
    pr.enable()
    pr.runcall(main)
    pr.disable()
    pr.dump_stats(str(Path(__file__).parent / "stats_no_init_name.log"))

    end = datetime.datetime.now()
    print(f"Total time: {end - start}")
