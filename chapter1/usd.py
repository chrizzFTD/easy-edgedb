"""
Some kind of City or Location type.
These types that we can create are called object types, made out of properties and links.
What properties should a City type have? Perhaps a name and a location, and sometimes a different name or spelling.
Bistritz for example is now called Bistrița (it's in Romania), and Buda-Pesth is now written Budapest.

Some kind of Person type. We need it to have a name, and also a way to track the places that the person visited.

"""
from grill import names
from pxr import Usd, Sdf, Ar


# class UsdFile(names.DateTimeFile, names.CGAssetFile):
class UsdFile(names.CGAssetFile):
    DEFAULT_SUFFIX = 'usda'


from pathlib import Path
repo = Path(__file__).parent / "assets"
import logging
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)
usdf = UsdFile.get_default(code='dracula')
LOG.info(f"Repository path: {repo}")
LOG.info(f"Stage identifier: {usdf}")
# we first create a layer under our repo
layer = Sdf.Layer.CreateNew(str(repo / usdf.name))
# delete it since it will have an identifier with the full path,
# and we want to have the identifier relative to the repository path
del layer
# to get the relative identifier, use an asset resolver context to load the layer
ctx = Ar.DefaultResolverContext([str(repo)])
with Ar.ResolverContextBinder(ctx):
    # stage's root layer identifier will now be relative to the repository path
    stage = Usd.Stage.Open(usdf.name)


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
  modern_name := 'Bistri?a'
};

INSERT Person {
  name := 'Jonathan Harker',
  places_visited := City,
};
"""

# types, types.
# this types should ideally come directly from EdgeDB? without reaching the database first?
from dataclasses import dataclass

@dataclass
class City:
    name: str
    display_name: str = ''
    modern_name: str = ''

@dataclass
class Person:
    name: str
    display_name: str = ''

munich = City('Munich')
budapest = City('Budapest', 'Buda-Pesth', 'Budapest',)
bistritz = City('Bistritz', 'Bistritz', 'Bistrița',)

tos = lambda: print(stage.GetRootLayer().ExportToString())
jonathan = Person('JonathanHarker', 'Jonathan Harker')

cityPath = Sdf.Path("/City")
personPath = Sdf.Path("/Person")
for rootPath, children in {
    cityPath: (munich, budapest, bistritz),
    personPath: (jonathan,),
}.items():
    for each in children:
        path = rootPath.AppendChild(each.name)
        prim = stage.DefinePrim(path)
        for datum in ('display_name', 'modern_name'):
            value = getattr(each, datum, None)
            if not value:
                continue
            prim.SetCustomDataByKey(datum, value)

"""
If you just want to return a single part of a type without the object structure, you can use . after the type name. For example, SELECT City.modern_name will give this output:

{'Budapest', 'Bistrița'}
"""

cityRoot = stage.GetPrimAtPath(cityPath)
print([p for p in Usd.PrimRange(cityRoot) if p.GetCustomDataByKey("modern_name")])
# [Usd.Prim(</City/Budapest>), Usd.Prim(</City/Bistritz>)]

"""
But we want to have Jonathan be connected to the cities he has traveled to. We'll change places_visited when we INSERT to places_visited := City:
"""

jonathanPrim = stage.GetPrimAtPath(personPath).GetPrimAtPath(jonathan.name)
jonathanVisitRel = jonathanPrim.CreateRelationship('places_visited')
for city in cityRoot.GetChildren():
    jonathanVisitRel.AddTarget(city.GetPath())

tos()
stage.GetRootLayer().Save()

if __name__ == "__main__":
    ...
