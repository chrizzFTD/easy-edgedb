import logging
from pathlib import Path

from grill import names

from pxr import UsdUtils, Usd, Sdf, Ar, Kind

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
repo = Path(__file__).parent / "assets"


class UsdFile(names.CGAssetFile):
    DEFAULT_SUFFIX = 'usda'


dracula_root_id = UsdFile.get_default(code='dracula')
logger.info(f"Repository path: {repo}")
logger.info(f"Stage identifier: {dracula_root_id}")


def fetch_stage(root_id) -> Usd.Stage:
    """For the given root layer identifier, get a corresponding stage.

    If layer does not exist, it is created in the repository.

    If a stage for the corresponding layer is found on the global cache, return it.
    Otherwise open it, populate the cache and return it.

    :param root_id:
    :return:
    """
    rootf = UsdFile(root_id)
    ctx = Ar.DefaultResolverContext([str(repo)])
    cache = UsdUtils.StageCache.Get()
    with Ar.ResolverContextBinder(ctx):
        layer_id = rootf.name
        layer = Sdf.Layer.Find(layer_id)
        if not layer:
            print(f"Layer {layer_id} was not found open. Attempting to open it.")
            if not Sdf.Layer.FindOrOpen(layer_id):
                print(f"Layer {layer_id} does not exist on repository path: {ctx.GetSearchPath()}. Creating a new one.")
                # we first create a layer under our repo
                tmp_new_layer = Sdf.Layer.CreateNew(str(repo / layer_id))
                # delete it since it will have an identifier with the full path,
                # and we want to have the identifier relative to the repository path
                # TODO: with AR 2.0 it should be possible to create in memory layers
                #   with relative identifers to that of the search path of the context.
                #   In the meantime, we need to create the layer first on disk.
                del tmp_new_layer
            stage = Usd.Stage.Open(layer_id)
            print(f"Opened stage: {stage}")
            cache_id = cache.Insert(stage)
            print(f"Added stage for {layer_id} with cache ID: {cache_id.ToString()}.")
        else:
            print(f"Layer was open. Found: {layer}")
            stage = cache.FindOneMatching(layer)
            if not stage:
                print(f"Could not find stage on the cache.")
                stage = Usd.Stage.Open(layer)
                cache_id = cache.Insert(stage)
                print(f"Added stage for {layer} with cache ID: {cache_id.ToString()}.")
            else:
                print(f"Found stage: {stage}")
    return stage


stage = fetch_stage(dracula_root_id)
assert stage is fetch_stage(dracula_root_id)

# types, types.
# this types should ideally come directly from EdgeDB? without reaching the database first?

db_root_path = Sdf.Path("/DBTypes")


def define_db_type(stage, name, references=None) -> Usd.Prim:
    stage_layer = stage.GetRootLayer()
    resolver_ctx = stage.GetPathResolverContext()
    current_asset_name = UsdFile(Path(stage.GetRootLayer().realPath).name)
    db_asset_name = current_asset_name.get(kingdom="db", item='types')
    db_stage = fetch_stage(db_asset_name)

    db_layer = db_stage.GetRootLayer()
    if db_layer.identifier not in stage_layer.subLayerPaths:
        stage_layer.subLayerPaths.append(db_layer.identifier)

    db_type_path = db_root_path.AppendChild(name)
    db_type = stage.GetPrimAtPath(db_type_path)
    if db_type:
        return db_type
    db_type = db_stage.DefinePrim(db_type_path)
    if references:
        for reference in references:
            db_type.GetReferences().AddInternalReference(reference.GetPath())
    return stage.GetPrimAtPath(db_type_path)

# TODO: what should person and place be? Assemblies vs components.
#   For now, only cities are considered assemblies.

# all DB definitions go to the db types asset.
displayable_type = define_db_type(stage, "DisplayableName")
transport_enum = define_db_type(stage, "Transport")
person_type = define_db_type(stage, "Person", (displayable_type,))
pc_type = define_db_type(stage, "PC", (person_type, transport_enum))
npc_type = define_db_type(stage, "NPC", (person_type,))
vampire_type = define_db_type(stage, "Vampire", (person_type,))
place_type = define_db_type(stage, "Place", (displayable_type,))
city_type = define_db_type(stage, "City", (place_type,))

# TODO: the following db relationships as well. This time we do this with an edit target
# with
displayable_type.CreateAttribute("display_name", Sdf.ValueTypeNames.String)
variant_set = transport_enum.GetVariantSets().AddVariantSet("Transport")
for set_name in ("Feet", "Train", "HorseDrawnCarriage"):
    variant_set.AddVariant(set_name)

person_type.CreateAttribute('age', Sdf.ValueTypeNames.Int2)
# TODO: how to add constraints? Useful to catch errors before they hit the database
#   https://github.com/edgedb/easy-edgedb/blob/master/chapter3/index.md#adding-constraints
person_type.CreateRelationship('places_visited')

place_type.CreateAttribute("modern_name", Sdf.ValueTypeNames.String)
country_type = define_db_type(stage, "Country", (place_type,))
for each in (city_type, country_type):
    # all places that end up in the database are "important places"
    Usd.ModelAPI(each).SetKind(Kind.Tokens.assembly)

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

hungary = create(stage, country_type, 'Hungary')
romania = create(stage, country_type, 'Romania')

jonathan = create(stage, pc_type, 'JonathanHarker', display_name='Jonathan Harker')
emil = create(stage, pc_type, "EmilSinclair", display_name="Emil Sinclair")
dracula = create(stage, vampire_type, 'CountDracula', display_name='Count Dracula')
dracula.GetRelationship('places_visited').AddTarget(romania.GetPath())

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


# DELETING
# try deleting the countries, this works as long as definitions are on the current edit target
# note how relationships still exist (since they're authored paths)
# country_root = stage.GetPrimAtPath(f"/{country_type.GetName()}")
# stage.RemovePrim(country_root.GetPath())

if __name__ == "__main__":
    # tos()
    # for prim in stage.Traverse(predicate=Usd.PrimIsModel):  # we'll see only "important" prims
    #     print(prim)
    #
    # # for x in range(5_000):
    # for x in range(5):
    #     create(stage, city_type, f'NewCity{x}', display_name=f"New City Hello {x}")
    #
    # stage.GetRootLayer().Save()
    stage.Save()

    def persist(stage):
        logger.info(f"Extracting information from f{stage} to persist on the database.")
        city_root = stage.GetPseudoRoot().GetPrimAtPath("City")
        for prim in city_root.GetChildren():
            print(prim)
    persist(stage)
