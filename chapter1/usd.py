"""
Some kind of City or Location type.
These types that we can create are called object types, made out of properties and links.
What properties should a City type have? Perhaps a name and a location, and sometimes a different name or spelling.
Bistritz for example is now called Bistrița (it's in Romania), and Buda-Pesth is now written Budapest.

Some kind of Person type. We need it to have a name, and also a way to track the places that the person visited.

"""
import logging
from pathlib import Path

from pxr import Sdf
from grill import write

repo = Path(__file__).parent / "assets"
token = write.repo.set(repo)

logging.basicConfig(level=logging.INFO)
logging.getLogger("grill").setLevel(logging.INFO)
logger = logging.getLogger(__name__)
root_asset = write.UsdAsset.get_default(code='dracula')

logger.info(f"Repository path: {repo}")
logger.info(f"Stage identifier: {root_asset}")

root_stage = write.fetch_stage(root_asset)

displayable_type = write.define_db_type(root_stage, "DisplayableName")

# TODO: the following db relationships as well. This time we do this with an edit target
db_layer = write.find_layer_matching(write._DB_TOKENS, root_stage.GetLayerStack())
city_type = write.define_db_type(root_stage, "City", (displayable_type,))
person_type = write.define_db_type(root_stage, "Person", (displayable_type,))

### DB edits  ###
with write.edit_context(db_layer, root_stage):
    displayable_type.CreateAttribute("display_name", Sdf.ValueTypeNames.String)
    city_type.CreateAttribute("modern_name", Sdf.ValueTypeNames.String)
    person_type.CreateRelationship('places_visited')

munich = write.create(root_stage, city_type, 'Munich')
budapest = write.create(root_stage, city_type, 'Budapest', display_name='Buda-Pesth')
bistritz = write.create(root_stage, city_type, 'Bistritz', display_name='Bistritz')

bistritz_layer = write.find_layer_matching(
        dict(item='Bistritz', kingdom='assets'), (stack.layer for stack in bistritz.GetPrimStack())
    )
with write.edit_context(bistritz, bistritz_layer, root_stage):
    bistritz.GetAttribute("modern_name").Set('Bistrița')


budapest_layer = write.find_layer_matching(
        dict(item='Budapest', kingdom='assets'), (stack.layer for stack in budapest.GetPrimStack())
    )
with write.edit_context(budapest, budapest_layer, root_stage):
    budapest.GetAttribute("modern_name").Set('Budapest!')

jonathan = write.create(root_stage, person_type, 'JonathanHarker', display_name='Jonathan Harker')

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

tos = lambda: print(root_stage.GetRootLayer().ExportToString())

"""
If you just want to return a single part of a type without the object structure, you can use . after the type name. For example, SELECT City.modern_name will give this output:

{'Budapest', 'Bistrița'}
"""
cityRoot = budapest.GetParent()
from pxr import Usd
print([p for p in Usd.PrimRange(cityRoot) if p.GetAttribute("modern_name").Get()])
# [Usd.Prim(</City/Budapest>), Usd.Prim(</City/Bistritz>)]

"""
But we want to have Jonathan be connected to the cities he has traveled to. We'll change places_visited when we INSERT to places_visited := City:
"""

jonathanVisitRel = jonathan.GetRelationship('places_visited')
for city in cityRoot.GetChildren():
    jonathanVisitRel.AddTarget(city.GetPath())

tos()
root_stage.Save()

if __name__ == "__main__":
    ...
