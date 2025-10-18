import logging
from pathlib import Path

from pxr import Sdf

from grill import cook, names
from grill.tokens import ids

logger = logging.getLogger(__name__)

names.UsdAsset.DEFAULT_SUFFIX = "usda"

cook.Repository.set(Path(__file__).parent / "assets")

stage = cook.fetch_stage(cook.UsdAsset.get_default(code='dracula'))

_OBJECT_FIELDS = {ids.CGAsset.kingdom.name: "Object"}

# we can define a taxon with or without an edit context
person = cook.define_taxon(stage, "Person", id_fields=_OBJECT_FIELDS)

with cook.taxonomy_context(stage):
    transport = cook.define_taxon(stage, "Transport", id_fields=_OBJECT_FIELDS)
    place = cook.define_taxon(stage, "Place", id_fields=_OBJECT_FIELDS)
    player = cook.define_taxon(stage, "Player", references=(person, transport))
    non_player = cook.define_taxon(stage, "NonPlayer", references=(person,))
    city = cook.define_taxon(stage, "City", references=(place,))
    vampire = cook.define_taxon(stage, "Vampire", references=(person,))
    country = cook.define_taxon(stage, "Country", references=(place,))

    # but to edit a category definition we must be in a taxonomy context
    place.CreateAttribute("modern_name", Sdf.ValueTypeNames.String)

    # Taxonomy does not define model hierarchy.
    # Model hierarchy is constructed when units assemble between each other.

    variant_set = transport.GetVariantSets().AddVariantSet("Transport")
    for set_name in ("Feet", "Train", "HorseDrawnCarriage"):
        variant_set.AddVariant(set_name)

    # Add a maximum limit of 120 for human ages
    age = person.CreateAttribute('age', Sdf.ValueTypeNames.Int)
    hard_limits = age.GetHardLimits()
    hard_limits.SetMaximum(120)
    person.CreateRelationship('places_visited')

cook.create_unit(city, 'Munich')
budapest, bistritz = cook.create_many(city, ('Budapest', 'Bistritz'), labels=('Buda-Pesth', 'Bistritz'))
golden_krone = cook.create_unit(place, 'GoldenKroneHotel', label='Golden Krone Hotel')
jonathan = cook.create_unit(person, 'JonathanHarker', label='Jonathan Harker')
emil = cook.create_unit(player, "EmilSinclair", label="Emil Sinclair")
dracula = cook.create_unit(vampire, 'CountDracula', label='Count Dracula')
hungary, romania = cook.create_many(country, ('Hungary', 'Romania'))

cook.spawn_unit(bistritz, golden_krone)

with cook.unit_context(bistritz):
    bistritz.GetAttribute("modern_name").Set('Bistrița')

with cook.unit_context(budapest):
    budapest.GetAttribute("modern_name").Set('Budapest!')

dracula.GetRelationship('places_visited').AddTarget(romania.GetPath())

"""
If you just want to return a single part of a type without the object structure, you can use . after the type name. For example, SELECT City.modern_name will give this output:

{'Budapest', 'Bistrița'}
"""
cities = cook.filter_taxa(stage.Traverse(), city)
print([p for p in cities if p.GetAttribute("modern_name").Get()])
# [Usd.Prim(</City/Budapest>), Usd.Prim(</City/Bistritz>)]

"""
But we want to have Jonathan be connected to the cities he has traveled to. We'll change places_visited when we INSERT to places_visited := City:
"""
for person, places in {
    jonathan: cities,
    emil: cities,
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

if __name__ == "__main__":
    stage.Save()

    def persist(stage):
        logger.info(f"Extracting information from f{stage} to persist on the database.")
        for prim in cities:
            logger.info(prim)
    persist(stage)

