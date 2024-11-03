"""
Some kind of City or Location type.
These types that we can create are called object types, made out of properties and links.
What properties should a City type have? Perhaps a name and a location, and sometimes a different name or spelling.
Bistritz for example is now called Bistrița (it's in Romania), and Buda-Pesth is now written Budapest.

Some kind of Person type. We need it to have a name, and also a way to track the places that the person visited.

"""
from pathlib import Path

from grill import cook, names
from pxr import Usd, Sdf, Kind

names.UsdAsset.DEFAULT_SUFFIX = "usda"

cook.Repository.set(Path(__file__).parent / "assets")

stage = cook.fetch_stage(cook.UsdAsset.get_default(code='dracula'))

# we can define a category with or without an edit context
person = cook.define_taxon(stage, "Person")

with cook.taxonomy_context(stage):
    transport = cook.define_taxon(stage, "Transport")
    player = cook.define_taxon(stage, "Player", references=(person, transport))
    non_player = cook.define_taxon(stage, "NonPlayer", references=(person,))
    place = cook.define_taxon(stage, "Place")
    city = cook.define_taxon(stage, "City", references=(place,))

    # but to edit a category definition we must be in a taxonomy context
    place.CreateAttribute("modern_name", Sdf.ValueTypeNames.String)
    person.CreateRelationship('places_visited')

    # TODO: what should person and place be? Assemblies vs components.
    #       For now, only cities are considered assemblies.
    # all places that end up in the database are "important places"
    Usd.ModelAPI(city).SetKind(Kind.Tokens.assembly)

    variant_set = transport.GetVariantSets().AddVariantSet("Transport")
    for set_name in ("Feet", "Train", "HorseDrawnCarriage"):
        variant_set.AddVariant(set_name)

cook.create_unit(city, 'Munich')
budapest = cook.create_unit(city, 'Budapest', label='Buda-Pesth')
bistritz = cook.create_unit(city, 'Bistritz', label='Bistritz')
golden_krone = cook.create_unit(place, 'GoldenKroneHotel', label='Golden Krone Hotel')
jonathan = cook.create_unit(person, 'JonathanHarker', label='Jonathan Harker')
emil = cook.create_unit(player, "EmilSinclair", label="Emil Sinclair")

with cook.unit_context(bistritz):
    bistritz.GetAttribute("modern_name").Set('Bistrița')

# we could set "important_places" as a custom new property
# but "important" prims are already provided by the USD model hierarchy.
# let's try it and see if we can get away with it.
# also, let's make it a child of bistritz. spawn_unit is enough.
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
}.items():
    visit_rel = person.GetRelationship('places_visited')
    for each in places:
        visit_rel.AddTarget(each.GetPath())

emil.GetVariantSet("Transport").SetVariantSelection("HorseDrawnCarriage")

if __name__ == "__main__":
    for prim in stage.Traverse(predicate=Usd.PrimIsModel):  # we'll see only "important" prims
        print(prim)
    stage.Save()
