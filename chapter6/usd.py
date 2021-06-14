import logging
import datetime
from pathlib import Path

from pxr import Usd, Sdf, Kind

from grill import write
from grill.tokens import ids

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def iter_taxa(stage, taxon1, *taxonN, predicate=Usd.PrimDefaultPredicate):
    """Iterate over prims that inherit from the given taxa."""
    it = iter(Usd.PrimRange.Stage(stage, predicate=predicate))
    taxa_names = {i if isinstance(i, str) else i.GetName() for i in (taxon1, *taxonN)}
    for prim in it:
        if prim.GetPath().HasPrefix(write._TAXONOMY_ROOT_PATH):
            # Ignore prims from the taxonomy hierarchy as they're not
            # taxa members but the definition themselves.
            it.PruneChildren()
        elif taxa_names.intersection(prim.GetCustomDataByKey(f'{write._PRIM_GRILL_KEY}:taxa') or {}):
            yield prim


def main():
    token = write.repo.set(Path(__file__).parent / "assets")

    stage = write.fetch_stage(write.UsdAsset.get_default(code='dracula'))

    # Define taxonomy
    _object_fields = {ids.CGAsset.kingdom.name: "Object"}
    with write.taxonomy_context(stage):
        person = write.define_taxon(stage, "Person", id_fields=_object_fields)
        transport = write.define_taxon(stage, "Transport", id_fields=_object_fields)
        place = write.define_taxon(stage, "Place", id_fields=_object_fields)
        player = write.define_taxon(stage, "Player", references=(person, transport))
        non_player = write.define_taxon(stage, "NonPlayer", references=(person,))
        vampire = write.define_taxon(stage, "Vampire", references=(person,))
        minor_vampire = write.define_taxon(stage, "MinorVampire", references=(person,))
        city = write.define_taxon(stage, "City", references=(place,))
        country = write.define_taxon(stage, "Country", references=(place,))
        other_place = write.define_taxon(stage, "OtherPlace", references=(place,))

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


    munich = write.create(city, 'Munich')
    budapest = write.create(city, 'Budapest', label='Buda-Pesth')
    bistritz = write.create(city, 'Bistritz', label='Bistritz')
    london = write.create(city, 'London')
    golden_krone = write.create(place, 'GoldenKroneHotel', label='Golden Krone Hotel')
    castle_dracula = write.create(other_place, 'CastleDracula', label='Castle Dracula')
    write.create(country, 'Hungary')
    write.create(country, 'France')
    write.create(country, 'Slovakia')

    romania = write.create(country, 'Romania')

    jonathan = write.create(person, 'JonathanHarker', label='Jonathan Harker')
    emil = write.create(player, "EmilSinclair", label="Emil Sinclair")
    dracula = write.create(vampire, 'CountDracula', label='Count Dracula')
    woman1 = write.create(minor_vampire, 'Woman01', label='Woman 1')
    woman2 = write.create(minor_vampire, 'Woman02', label='Woman 2')
    woman3 = write.create(minor_vampire, 'Woman03', label='Woman 3')
    for each in woman1, woman2, woman3:
        dracula.GetRelationship("slaves").AddTarget(each.GetPath())
    mina = write.create(non_player, 'MinaMurray', label='Mina Murray')
    mina.GetRelationship("lover").AddTarget(jonathan.GetPath())
    jonathan.GetRelationship("lover").AddTarget(mina.GetPath())

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

    with write.unit_context(romania):
        instanced_castle = stage.OverridePrim(romania.GetPath().AppendChild(castle_dracula.GetName()))
        castle_dracula_layer = write.unit_asset(castle_dracula)
        # TODO: should this be a payload or a reference?
        instanced_castle.GetPayloads().AddPayload(castle_dracula_layer.identifier)
        Usd.ModelAPI(instanced_castle).SetKind(Kind.Tokens.component)  # should be component or assembly?

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
    list(iter_taxa(stage, place))

    for person, places in {
        # jonathan: city_root.GetChildren(),
        jonathan: [munich, budapest, bistritz, london, romania, castle_dracula],
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

    # # for x in range(1_000):
    # for x in range(10):
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

    ### Time to practice ###
    # 1. How would you complete it so that it says "Pleased to meet you, I'm " and then the NPC's name?
    for each in iter_taxa(stage, "NonPlayer", predicate=Usd.PrimAllPrimsPredicate):
        print(f"Pleased to meet you, I'm {each.GetName()}")

    # 2. How would you update Mina's `places_visited` to include Romania if she went to Castle Dracula for a visit?
    mina = next(iter_taxa(stage, "NonPlayer"), None)
    assert mina is not None
    from pprint import pprint
    mina_places = mina.GetRelationship("places_visited")
    for each in iter_taxa(stage, "Place"):
        if each.GetName() in {"CastleDracula", "Romania"}:
            print(f"Adding {each}")
            mina_places.AddTarget(each.GetPath())

    # 3. With the set `{'W', 'J', 'C'}`, how would you display all the `Person` types with a name that contains any of these capital letters?
    letters = {'W', 'J', 'C'}
    pprint([i for i in iter_taxa(stage, 'Person') if letters.intersection(each.GetName())])

    # 5. How would you add ' the Great' to every Person type?
    for each in iter_taxa(stage, 'Person'):
        label = each.GetAttribute('label')
        label.Set(label.Get() + ' the Great')
        print(label.Get())
