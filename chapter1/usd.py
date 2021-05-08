"""
Some kind of City or Location type.
These types that we can create are called object types, made out of properties and links.
What properties should a City type have? Perhaps a name and a location, and sometimes a different name or spelling.
Bistritz for example is now called Bistrița (it's in Romania), and Buda-Pesth is now written Budapest.

Some kind of Person type. We need it to have a name, and also a way to track the places that the person visited.

"""
from pathlib import Path

from grill import write
from pxr import Sdf, Usd

write.repo.set(Path(__file__).parent / "assets")

stage = write.fetch_stage(write.UsdAsset.get_default(code='dracula'))

# we can define a category with or without an edit context
displayable = write.define_taxon(stage, "DisplayableName")
city = write.define_taxon(stage, "City", references=(displayable,))

with write.taxonomy_context(stage):
    person = write.define_taxon(stage, "Person", references=(displayable,))
    # but to edit a category definition we must be in the proper context
    displayable.CreateAttribute("label", Sdf.ValueTypeNames.String)
    city.CreateAttribute("modern_name", Sdf.ValueTypeNames.String)
    person.CreateRelationship('places_visited')

write.create(city, 'Munich')
budapest = write.create(city, 'Budapest', label='Buda-Pesth')
bistritz = write.create(city, 'Bistritz', label='Bistritz')
jonathan = write.create(person, 'JonathanHarker', label='Jonathan Harker')

"""

INSERT City {
  name := 'Munich',
};

INSERT City {
  name := 'Buda-Pesth',
  modern_name := 'Budapest'
};

INSERT City {
  name := 'Bistritz',
  modern_name := 'Bistrița'
};

INSERT Person {
  name := 'Jonathan Harker',
  places_visited := City,
};
"""

with write.asset_context(bistritz):
    bistritz.GetAttribute("modern_name").Set('Bistrița')

with write.asset_context(budapest):
    budapest.GetAttribute("modern_name").Set('Budapest!')

"""
If you just want to return a single part of a type without the object structure, you can use . after the type name. For example, SELECT City.modern_name will give this output:

{'Budapest', 'Bistrița'}
"""
city_root = stage.GetPseudoRoot().GetPrimAtPath(city.GetName())
print([p for p in Usd.PrimRange(city_root) if p.GetAttribute("modern_name").Get()])
# [Usd.Prim(</City/Budapest>), Usd.Prim(</City/Bistritz>)]

"""
But we want to have Jonathan be connected to the cities he has traveled to. We'll change places_visited when we INSERT to places_visited := City:
"""

jonathanVisitRel = jonathan.GetRelationship('places_visited')
for city in city_root.GetChildren():
    jonathanVisitRel.AddTarget(city.GetPath())

stage.Save()

if __name__ == "__main__":
    ...
