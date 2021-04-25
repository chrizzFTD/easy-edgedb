"""
Some kind of City or Location type.
These types that we can create are called object types, made out of properties and links.
What properties should a City type have? Perhaps a name and a location, and sometimes a different name or spelling.
Bistritz for example is now called Bistrița (it's in Romania), and Buda-Pesth is now written Budapest.

Some kind of Person type. We need it to have a name, and also a way to track the places that the person visited.

"""
from pathlib import Path

from grill import write
from pxr import Usd, Sdf, Kind

write.repo.set(Path(__file__).parent / "assets")

stage = write.fetch_stage(write.UsdAsset.get_default(code='dracula'))

# we can define a category with or without an edit context
displayable = write.define_category(stage, "DisplayableName")

with write.category_context(stage):
    # but to edit a category definition we must be in the proper context
    person = write.define_category(stage, "Person", references=(displayable,))
    transport = write.define_category(stage, "Transport")
    player = write.define_category(stage, "Player", references=(person, transport))
    non_player = write.define_category(stage, "NonPlayer", references=(person,))
    place = write.define_category(stage, "Place", references=(displayable,))

    displayable.CreateAttribute("display_name", Sdf.ValueTypeNames.String)
    place.CreateAttribute("modern_name", Sdf.ValueTypeNames.String)
    person.CreateRelationship('places_visited')

    city = write.define_category(stage, "City", references=(place,))

    # TODO: what should person and place be? Assemblies vs components.
    #       For now, only cities are considered assemblies.
    # all places that end up in the database are "important places"
    Usd.ModelAPI(city).SetKind(Kind.Tokens.assembly)

    variant_set = transport.GetVariantSets().AddVariantSet("Transport")
    for set_name in ("Feet", "Train", "HorseDrawnCarriage"):
        variant_set.AddVariant(set_name)

write.create(city, 'Munich')
budapest = write.create(city, 'Budapest', display_name='Buda-Pesth')
bistritz = write.create(city, 'Bistritz', display_name='Bistritz')
jonathan = write.create(person, 'JonathanHarker', display_name='Jonathan Harker')
emil = write.create(player, "EmilSinclair", display_name="Emil Sinclair")

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
emil.GetVariantSet("Transport").SetVariantSelection("HorseDrawnCarriage")


if __name__ == "__main__":
    for prim in stage.Traverse(predicate=Usd.PrimIsModel):  # we'll see only "important" prims
        print(prim)
    stage.Save()
