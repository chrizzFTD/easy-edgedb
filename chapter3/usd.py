import logging
from pathlib import Path

from pxr import Usd, Sdf, Kind

from grill import write
from grill.tokens import ids

logger = logging.getLogger(__name__)

write.repo.set(Path(__file__).parent / "assets")

stage = write.fetch_stage(write.UsdAsset.get_default(code='dracula'))

_OBJECT_FIELDS = {ids.CGAsset.kingdom.name: "Object"}

# we can define a category with or without an edit context
person = write.define_taxon(stage, "Person", id_fields=_OBJECT_FIELDS)

with write.taxonomy_context(stage):
    transport = write.define_taxon(stage, "Transport", id_fields=_OBJECT_FIELDS)
    place = write.define_taxon(stage, "Place", id_fields=_OBJECT_FIELDS)
    player = write.define_taxon(stage, "Player", references=(person, transport))
    non_player = write.define_taxon(stage, "NonPlayer", references=(person,))
    city = write.define_taxon(stage, "City", references=(place,))
    vampire = write.define_taxon(stage, "Vampire", references=(person,))
    country = write.define_taxon(stage, "Country", references=(place,))

    # but to edit a category definition we must be in a taxonomy context
    place.CreateAttribute("modern_name", Sdf.ValueTypeNames.String)

    # TODO: what should person and place be? Assemblies vs components.
    #       For now, only cities are considered assemblies.
    # all places that end up in the database are "important places"
    for each in (city, country):
        # all places that end up in the database are "important places"
        Usd.ModelAPI(each).SetKind(Kind.Tokens.assembly)

    variant_set = transport.GetVariantSets().AddVariantSet("Transport")
    for set_name in ("Feet", "Train", "HorseDrawnCarriage"):
        variant_set.AddVariant(set_name)

    # TODO: how to add constraints? Useful to catch errors before they hit the database
    #   https://github.com/edgedb/easy-edgedb/blob/master/chapter3/index.md#adding-constraints
    person.CreateAttribute('age', Sdf.ValueTypeNames.Int2)
    person.CreateRelationship('places_visited')

write.create(city, 'Munich')
budapest = write.create(city, 'Budapest', label='Buda-Pesth')
bistritz = write.create(city, 'Bistritz', label='Bistritz')
golden_krone = write.create(place, 'GoldenKroneHotel', label='Golden Krone Hotel')
jonathan = write.create(person, 'JonathanHarker', label='Jonathan Harker')
emil = write.create(player, "EmilSinclair", label="Emil Sinclair")
dracula = write.create(vampire, 'CountDracula', label='Count Dracula')
hungary = write.create(country, 'Hungary')
romania = write.create(country, 'Romania')

with write.unit_context(bistritz):
    bistritz.GetAttribute("modern_name").Set('Bistrița')
    # we could set "important_places" as a custom new property
    # but "important" prims are already provided by the USD model hierarchy.
    # let's try it and see if we can get away with it.
    # also, let's make it a child of bistritz
    instanced_krone = stage.OverridePrim(bistritz.GetPath().AppendChild(golden_krone.GetName()))
    golden_krone_layer = write.unit_asset(golden_krone)
    instanced_krone.GetReferences().AddReference(golden_krone_layer.identifier)
    Usd.ModelAPI(instanced_krone).SetKind(Kind.Tokens.component)  # should be component or assembly?


with write.unit_context(budapest):
    budapest.GetAttribute("modern_name").Set('Budapest!')

dracula.GetRelationship('places_visited').AddTarget(romania.GetPath())

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

if __name__ == "__main__":
    # tos()
    # for prim in stage.Traverse(predicate=Usd.PrimIsModel):  # we'll see only "important" prims
    #     logger.info(prim)
    #
    # # for x in range(5_000):
    # for x in range(5):
    #     easyedb.create(stage, city_type, f'NewCity{x}', label=f"New City Hello {x}")
    #
    # stage.GetRootLayer().Save()
    stage.Save()

    def persist(stage):
        logger.info(f"Extracting information from f{stage} to persist on the database.")
        city_root = stage.GetPseudoRoot().GetPrimAtPath("City")
        for prim in city_root.GetChildren():
            logger.info(prim)
    persist(stage)
    # code that uses 'var'; var.get() returns 'new value'. Call at the end.
