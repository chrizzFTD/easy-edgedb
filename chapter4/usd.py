import logging
import datetime
from pathlib import Path

from pxr import Usd, Sdf, Kind

from grill import write
from grill.tokens import ids

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    token = write.repo.set(Path(__file__).parent / "assets")

    stage = write.fetch_stage(write.UsdAsset.get_default(code='dracula'))

    _object_fields = {ids.CGAsset.kingdom.name: "Object"}
    # we can define a category with or without an edit context
    person = write.define_taxon(stage, "Person", id_fields=_object_fields)

    with write.taxonomy_context(stage):
        transport = write.define_taxon(stage, "Transport", id_fields=_object_fields)
        place = write.define_taxon(stage, "Place", id_fields=_object_fields)

        player = write.define_taxon(stage, "Player", references=(person, transport))
        non_player = write.define_taxon(stage, "NonPlayer", references=(person,))
        vampire = write.define_taxon(stage, "Vampire", references=(person,))

        city = write.define_taxon(stage, "City", references=(place,))
        country = write.define_taxon(stage, "Country", references=(place,))

        # but to edit a category definition we must be in the proper context
        # TODO: what should person and place be? Assemblies vs components.
        #       For now, only cities are considered assemblies.
        # all places that end up in the database are "important places"
        for each in (city, country):
            # all places that end up in the database are "important places"
            Usd.ModelAPI(each).SetKind(Kind.Tokens.assembly)

        # TODO: how to add constraints? Useful to catch errors before they hit the database
        #   https://github.com/edgedb/easy-edgedb/blob/master/chapter3/index.md#adding-constraints
        person.CreateAttribute('age', Sdf.ValueTypeNames.Int2)
        place.CreateAttribute("modern_name", Sdf.ValueTypeNames.String)

        person.CreateRelationship('lover')
        person.CreateRelationship('places_visited')

        variant_set = transport.GetVariantSets().AddVariantSet("Transport")
        for set_name in ("Feet", "Train", "HorseDrawnCarriage"):
            variant_set.AddVariant(set_name)

    write.create(city, 'Munich')
    budapest = write.create(city, 'Budapest', label='Buda-Pesth')
    bistritz = write.create(city, 'Bistritz', label='Bistritz')
    london = write.create(city, 'London')
    golden_krone = write.create(place, 'GoldenKroneHotel', label='Golden Krone Hotel')
    write.create(country, 'Hungary')
    romania = write.create(country, 'Romania')

    jonathan = write.create(person, 'JonathanHarker', label='Jonathan Harker')
    emil = write.create(player, "EmilSinclair", label="Emil Sinclair")
    dracula = write.create(vampire, 'CountDracula', label='Count Dracula')
    mina = write.create(non_player, 'MinaMurray', label='Mina Murray')

    mina.GetRelationship("lover").AddTarget(jonathan.GetPath())

    with write.unit_context(bistritz):
        bistritz.GetAttribute("modern_name").Set('Bistrița')
        # we could set "important_places" as a custom new property
        # but "important" prims are already provided by the USD model hierarchy.
        # let's try it and see if we can get away with it.
        # also, let's make it a child of bistritz
        instanced_krone = stage.OverridePrim(bistritz.GetPath().AppendChild(golden_krone.GetName()))
        golden_krone_layer = write.unit_asset(golden_krone)
        # TODO: should this be a payload or a reference?
        instanced_krone.GetPayloads().AddPayload(golden_krone_layer.identifier)
        Usd.ModelAPI(instanced_krone).SetKind(Kind.Tokens.component)  # should be component or assembly?

    with write.unit_context(budapest):
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

    with write.unit_context(emil):
        emil.GetVariantSet("Transport").SetVariantSelection("HorseDrawnCarriage")

    # DELETING
    # try deleting the countries, this works as long as definitions are on the current edit target
    # note how relationships still exist (since they're authored paths)
    # country_root = stage.GetPrimAtPath(f"/{city_type.GetName()}")
    # stage.RemovePrim(country_root.GetPath())

    # 4 Questions / Unresolved
    # Time type, needed? Has "awake" property  driven by hour ( awake < 7am asleep < 19h awake

    # for x in range(1_000):
    #     # atm creating 1_000 new cities (including each USD file) takes around 7 seconds.
    #     # Total time: 0:00:06.993190
    #     # could be faster.
    #     write.create(city, f'NewCity{x}', label=f"New City Hello {x}")

    stage.Save()
    write.repo.reset(token)
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
