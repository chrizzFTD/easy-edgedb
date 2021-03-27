import logging
from pathlib import Path

from pxr import Usd, Sdf, Kind

from grill import easyedb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dracula_root_id = easyedb.UsdFile.get_default(code='dracula')

token = easyedb.repo.set(Path(__file__).parent / "repo")


logger.info(f"Repository path: {easyedb.repo.get()}")
logger.info(f"Stage identifier: {dracula_root_id}")

stage = easyedb.fetch_stage(dracula_root_id)
tos = lambda: logger.info(stage.GetRootLayer().ExportToString())

assert stage is easyedb.fetch_stage(dracula_root_id)

# types, types.
# this types should ideally come directly from EdgeDB? without reaching the database first?

# TODO: what should person and place be? Assemblies vs components.
#   For now, only cities are considered assemblies.

# all DB definitions go to the db types asset.
displayable_type = easyedb.define_db_type(stage, "DisplayableName")
transport_enum = easyedb.define_db_type(stage, "Transport")
person_type = easyedb.define_db_type(stage, "Person", (displayable_type,))
pc_type = easyedb.define_db_type(stage, "PC", (person_type, transport_enum))
npc_type = easyedb.define_db_type(stage, "NPC", (person_type,))
vampire_type = easyedb.define_db_type(stage, "Vampire", (person_type,))
place_type = easyedb.define_db_type(stage, "Place", (displayable_type,))
country_type = easyedb.define_db_type(stage, "Country", (place_type,))
city_type = easyedb.define_db_type(stage, "City", (place_type,))

# TODO: the following db relationships as well. This time we do this with an edit target
db_layer = easyedb._first_matching(easyedb.DB_TOKENS, stage.GetLayerStack())

### DB edits  ###
with easyedb.edit_context(db_layer, stage):
    displayable_type.CreateAttribute("display_name", Sdf.ValueTypeNames.String)
    variant_set = transport_enum.GetVariantSets().AddVariantSet("Transport")
    for set_name in ("Feet", "Train", "HorseDrawnCarriage"):
        variant_set.AddVariant(set_name)

    # TODO: how to add constraints? Useful to catch errors before they hit the database
    #   https://github.com/edgedb/easy-edgedb/blob/master/chapter3/index.md#adding-constraints
    person_type.CreateAttribute('age', Sdf.ValueTypeNames.Int2)
    person_type.CreateRelationship('places_visited')

    place_type.CreateAttribute("modern_name", Sdf.ValueTypeNames.String)
    for each in (city_type, country_type):
        # all places that end up in the database are "important places"
        Usd.ModelAPI(each).SetKind(Kind.Tokens.assembly)

### DB END ###

pseudoRootPath = stage.GetPseudoRoot().GetPath()
cityRoot = stage.DefinePrim(f"/{city_type.GetName()}")

munich = easyedb.create(stage, city_type, 'Munich')
budapest = easyedb.create(stage, city_type, 'Budapest', display_name='Buda-Pesth')
bistritz = easyedb.create(stage, city_type, 'Bistritz', display_name='Bistritz')

bistritz_layer = easyedb._first_matching(
    dict(item='Bistritz', kingdom='assets'), (stack.layer for stack in bistritz.GetPrimStack())
)

# We need to explicitely construct our edit target since our layer is not on the layer stack of the stage.

# editTarget = Usd.EditTarget(bistritz_layer, bistritz.GetPrimIndex().rootNode.children[0])
# with Usd.EditContext(stage, editTarget):
with easyedb.edit_context(bistritz, bistritz_layer, stage):
    bistritz.GetAttribute("modern_name").Set('Bistrița')

hungary = easyedb.create(stage, country_type, 'Hungary')
romania = easyedb.create(stage, country_type, 'Romania')

jonathan = easyedb.create(stage, pc_type, 'JonathanHarker', display_name='Jonathan Harker')
emil = easyedb.create(stage, pc_type, "EmilSinclair", display_name="Emil Sinclair")
dracula = easyedb.create(stage, vampire_type, 'CountDracula', display_name='Count Dracula')
dracula.GetRelationship('places_visited').AddTarget(romania.GetPath())


"""
If you just want to return a single part of a type without the object structure, you can use . after the type name. For example, SELECT City.modern_name will give this output:

{'Budapest', 'Bistrița'}
"""

# cityRoot = stage.GetPrimAtPath(cityPath)
logger.info([p for p in Usd.PrimRange(cityRoot) if p.GetAttribute("modern_name").IsValid() and p.GetAttribute("modern_name").Get()])
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
goldenKrone = easyedb.create(stage, place_type, 'GoldenKroneHotel', 'Golden Krone Hotel')
# also, let's make it a child of bistritz
childPrim = stage.OverridePrim(bistritz.GetPath().AppendChild(goldenKrone.GetName()))
childPrim.GetReferences().AddInternalReference(goldenKrone.GetPath())
Usd.ModelAPI(childPrim).SetKind(Kind.Tokens.component)  # should be component or reference?

emil_layer = easyedb._first_matching(
    dict(item='EmilSinclair', kingdom='assets'), (stack.layer for stack in emil.GetPrimStack())
)

# We need to explicitely construct our edit target since our layer is not on the layer stack of the stage.
# editTarget = Usd.EditTarget(emil_layer, emil.GetPrimIndex().rootNode.children[0])
# with Usd.EditContext(stage, editTarget):
with easyedb.edit_context(emil, emil_layer, stage):
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
    #     easyedb.create(stage, city_type, f'NewCity{x}', display_name=f"New City Hello {x}")
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
    easyedb.repo.reset(token)
