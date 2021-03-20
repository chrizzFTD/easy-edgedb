"""
Some kind of City or Location type.
These types that we can create are called object types, made out of properties and links.
What properties should a City type have? Perhaps a name and a location, and sometimes a different name or spelling.
Bistritz for example is now called Bistrița (it's in Romania), and Buda-Pesth is now written Budapest.

Some kind of Person type. We need it to have a name, and also a way to track the places that the person visited.

"""
import logging
from pathlib import Path

from grill import names

from pxr import Usd, Sdf, Ar, Kind

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
repo = Path(__file__).parent / "assets"


class UsdFile(names.CGAssetFile):
    DEFAULT_SUFFIX = 'usda'


dracula_root_id = UsdFile.get_default(code='dracula')
logger.info(f"Repository path: {repo}")
logger.info(f"Stage identifier: {dracula_root_id}")


def open_stage(root_id) -> Usd.Stage:
    rootf = UsdFile(root_id)
    # we first create a layer under our repo
    layer = Sdf.Layer.CreateNew(str(repo / rootf.name))
    # delete it since it will have an identifier with the full path,
    # and we want to have the identifier relative to the repository path
    del layer
    # to get the relative identifier, use an asset resolver context to load the layer
    ctx = Ar.DefaultResolverContext([str(repo)])
    with Ar.ResolverContextBinder(ctx):
        # stage's root layer identifier will now be relative to the repository path
        return Usd.Stage.Open(rootf.name)


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

stage = open_stage(dracula_root_id)

db_root = stage.DefinePrim("/DBTypes")
db_root_path = db_root.GetPath()

# TODO: what should person and place be? Assemblies vs components.
#       For now, only cities are considered assemblies.

displayable_type = stage.DefinePrim(db_root_path.AppendChild("DisplayableName"))
displayable_type.CreateAttribute("display_name", Sdf.ValueTypeNames.String)

transport_enum = stage.DefinePrim(db_root_path.AppendChild("Transport"))
variant_set = transport_enum.GetVariantSets().AddVariantSet("Transport")
for set_name in ("Feet", "Train", "HorseDrawnCarriage"):
    variant_set.AddVariant(set_name)


person_type = stage.DefinePrim(db_root_path.AppendChild("Person"))
person_type.CreateRelationship('places_visited')

pc_type = stage.DefinePrim(db_root_path.AppendChild("PC"))
for reference in (person_type.GetPath(), transport_enum.GetPath()):
    pc_type.GetReferences().AddInternalReference(reference)

npc_type = stage.DefinePrim(db_root_path.AppendChild("PC"))
npc_type.GetReferences().AddInternalReference(person_type.GetPath())

place_type = stage.DefinePrim(db_root_path.AppendChild("Place"))
place_type.CreateAttribute("modern_name", Sdf.ValueTypeNames.String)

city_type = stage.DefinePrim(db_root_path.AppendChild("City"))
city_type.GetReferences().AddInternalReference(place_type.GetPath())
# all places that end up in the database are "important places"
Usd.ModelAPI(city_type).SetKind(Kind.Tokens.assembly)

for db_type in (person_type, place_type, city_type):
    db_type.GetReferences().AddInternalReference(displayable_type.GetPath())

pseudoRootPath = stage.GetPseudoRoot().GetPath()
cityRoot = stage.DefinePrim(f"/{city_type.GetName()}")


def create(stage, dbtype, name, display_name=""):
    # contract: all dbtypes have a display_name
    scope_path = pseudoRootPath.AppendPath(dbtype.GetName())
    scope = stage.GetPrimAtPath(scope_path)
    if not scope:
        scope = stage.DefinePrim(scope_path)
    if not scope.IsModel():
        Usd.ModelAPI(scope).SetKind(Kind.Tokens.assembly)
    path = scope_path.AppendChild(name)
    prim = stage.DefinePrim(path)
    prim.GetReferences().AddInternalReference(dbtype.GetPath())
    if display_name:
        prim.GetAttribute("display_name").Set(display_name)
    return prim


munich = create(stage, city_type, 'Munich')
budapest = create(stage, city_type, 'Budapest', display_name='Buda-Pesth')
bistritz = create(stage, city_type, 'Bistritz', display_name='Bistritz')
bistritz.GetAttribute("modern_name").Set('Bistrița')

jonathan = create(stage, pc_type, 'JonathanHarker', display_name='Jonathan Harker')
emil = create(stage, pc_type, "EmilSinclair", display_name="Emil Sinclair")

tos = lambda: print(stage.GetRootLayer().ExportToString())


"""
If you just want to return a single part of a type without the object structure, you can use . after the type name. For example, SELECT City.modern_name will give this output:

{'Budapest', 'Bistrița'}
"""

# cityRoot = stage.GetPrimAtPath(cityPath)
print([p for p in Usd.PrimRange(cityRoot) if p.GetAttribute("modern_name").IsValid() and p.GetAttribute("modern_name").Get()])
# [Usd.Prim(</City/Budapest>), Usd.Prim(</City/Bistritz>)]

"""
But we want to have Jonathan be connected to the cities he has traveled to. We'll change places_visited when we INSERT to places_visited := City:
"""


for prim, places in {
    jonathan: cityRoot.GetChildren(),
    emil: cityRoot.GetChildren(),
}.items():
    visitRel = prim.GetRelationship('places_visited')
    for place in places:
        visitRel.AddTarget(place.GetPath())


# we could set "important_places" as a custom new property
# but "important" prims are already provided by the USD model hierarchy.
# let's try it and see if we can get away with it.
goldenKrone = create(stage, place_type, 'GoldenKroneHotel', 'Golden Krone Hotel')
# also, let's make it a child of bistritz
childPrim = stage.OverridePrim(bistritz.GetPath().AppendChild(goldenKrone.GetName()))
childPrim.GetReferences().AddInternalReference(goldenKrone.GetPath())
Usd.ModelAPI(childPrim).SetKind(Kind.Tokens.component)  # should be component or reference?
emil.GetVariantSet("Transport").SetVariantSelection("HorseDrawnCarriage")


if __name__ == "__main__":
    tos()
    for prim in stage.Traverse(predicate=Usd.PrimIsModel):  # we'll see only "important" prims
        print(prim)
    stage.GetRootLayer().Save()
