import logging
import datetime
from pathlib import Path

from pxr import Usd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    main_stage = Usd.Stage.CreateInMemory()
    class_stage = Usd.Stage.CreateInMemory()
    class_layer = class_stage.GetRootLayer()
    main_layer = main_stage.GetRootLayer()
    main_layer.subLayerPaths.append(class_layer.identifier)
    with Usd.EditContext(main_stage, class_layer):
        parent_class = main_stage.DefinePrim("/Classes/Base")

    objects_stage = Usd.Stage.CreateInMemory()
    objects_layer = objects_stage.GetRootLayer()
    main_layer.subLayerPaths.append(objects_layer.identifier)

    object_1_stage = Usd.Stage.CreateInMemory()
    object_1_layer = object_1_stage.GetRootLayer()
    object_1_stage.CreateClassPrim("/Classes")
    object_1_layer.subLayerPaths.append(class_layer.identifier)
    object_1_layer.subLayerPaths.append(objects_layer.identifier)

    object_1_default = object_1_stage.DefinePrim("/DefaultPrim")
    object_1_default.GetInherits().AddInherit(parent_class.GetPath())
    object_1_stage.SetDefaultPrim(object_1_default)

    object_2_stage = Usd.Stage.CreateInMemory()
    object_2_layer = object_2_stage.GetRootLayer()
    object_2_stage.CreateClassPrim("/Classes")
    object_2_layer.subLayerPaths.append(class_layer.identifier)
    object_2_layer.subLayerPaths.append(objects_layer.identifier)

    object_2_default = object_2_stage.DefinePrim("/DefaultPrim")
    object_2_default.GetInherits().AddInherit(parent_class.GetPath())
    object_2_stage.SetDefaultPrim(object_2_default)

    with Usd.EditContext(main_stage, objects_layer):
        object_1 = main_stage.DefinePrim("/Object/One")
        object_1.GetReferences().AddReference(object_1_layer.identifier)
        object_2 = main_stage.DefinePrim("/Object/Two")
        object_2.GetReferences().AddReference(object_2_layer.identifier)

    # query = Usd.PrimCompositionQuery(object_1)
    # for arc in query.GetCompositionArcs():
    #     print('-----------------------')
    #     print(f"{arc.GetArcType()=}")
    #     print(f"{arc.GetIntroducingLayer()=}")
    #     if arc.GetIntroducingLayer():
    #         print(arc.GetIntroducingLayer().ExportToString())
    #     print(f"{arc.GetIntroducingListEditor()=}")
    #     print(f"{arc.GetIntroducingNode()=}")
    #     print(f"{arc.GetIntroducingPrimPath()=}")
    #     print(f"{arc.GetTargetNode()=}")
    #     print(f"{arc.HasSpecs()=}")
    #     print(f"{arc.IsAncestral()=}")
    #     print(f"{arc.IsImplicit()=}")
    #     print(f"{arc.IsIntroducedInRootLayerPrimSpec()=}")
    #     print(f"{arc.IsIntroducedInRootLayerStack()=}")
    #     target_node = arc.GetTargetNode()
    #     print(f">>>>>>>>>>>>>>> {object_1_layer in target_node.layerStack.layers=}")
    #     print(f'{target_node.CanContributeSpecs()=}')
    #     print(f'{target_node.GetDepthBelowIntroduction()=}')
    #     print(f'{target_node.GetIntroPath()=}')
    #     print(f'{target_node.GetOriginRootNode()=}')
    #     print(f'{target_node.GetPathAtIntroduction()=}')
    #     print(f'{target_node.GetRootNode()=}')
    #     print(f'{target_node.IsDueToAncestor()=}')
    #     print(f'{target_node.IsRootNode()=}')
    #     print(f'{target_node.arcType=}')
    #     print(f'{target_node.children=}')
    #     print(f'{target_node.hasSpecs=}')
    #     print(f'{target_node.hasSymmetry=}')
    #     print(f'{target_node.isCulled=}')
    #     print(f'{target_node.isInert=}')
    #     print(f'{target_node.isRestricted=}')
    #     print(f'{target_node.layerStack=}')
    #     print(f'{target_node.mapToParent=}')
    #     print(f'{target_node.mapToRoot=}')
    #     print(f'{target_node.namespaceDepth=}')
    #     print(f'{target_node.origin=}')
    #     print(f'{target_node.parent=}')
    #     print(f'{target_node.path=}')
    #     print(f'{target_node.permission=}')
    #     print(f'{target_node.siblingNumAtOrigin=}')
    #     print(f'{target_node.site=}')
    #     intro_node = arc.GetIntroducingNode()
    #     print(f">>>>>>>>>>>>>>> {object_1_layer in intro_node.layerStack.layers=}")
    #     print(f'{intro_node.CanContributeSpecs()=}')
    #     print(f'{intro_node.GetDepthBelowIntroduction()=}')
    #     print(f'{intro_node.GetIntroPath()=}')
    #     print(f'{intro_node.GetOriginRootNode()=}')
    #     print(f'{intro_node.GetPathAtIntroduction()=}')
    #     print(f'{intro_node.GetRootNode()=}')
    #     print(f'{intro_node.IsDueToAncestor()=}')
    #     print(f'{intro_node.IsRootNode()=}')
    #     print(f'{intro_node.arcType=}')
    #     print(f'{intro_node.children=}')
    #     print(f'{intro_node.hasSpecs=}')
    #     print(f'{intro_node.hasSymmetry=}')
    #     print(f'{intro_node.isCulled=}')
    #     print(f'{intro_node.isInert=}')
    #     print(f'{intro_node.isRestricted=}')
    #     print(f'{intro_node.layerStack=}')
    #     print(f'{intro_node.mapToParent=}')
    #     print(f'{intro_node.mapToRoot=}')
    #     print(f'{intro_node.namespaceDepth=}')
    #     print(f'{intro_node.origin=}')
    #     print(f'{intro_node.parent=}')
    #     print(f'{intro_node.path=}')
    #     print(f'{intro_node.permission=}')
    #     print(f'{intro_node.siblingNumAtOrigin=}')
    #     print(f'{intro_node.site=}')
    # # for arc in query.GetCompositionArcs():
    # #     # target_node = arc.GetTargetNode()
    # #     # contract: we consider the "unit" target node the one matching origin path and the given layer
    # #     # if target_node.path == object_1_default.GetPath() and target_node.layerStack.identifier.rootLayer == object_1_layer:
    # #     node = arc.GetTargetNode()
    # #     # if node.GetPathAtIntroduction() == object_1_default.GetPath() and object_1_layer in node.layerStack.layers:
    # #     if object_1_layer in node.layerStack.layers:
    # #         print(f" <<<<<<<<<< FOOOOOOUND {arc.GetArcType()}")
    # #         target_node = node
    # #         break
    # # else:
    # #     raise ValueError(f"Could not find appropriate node for edit target for {object_1_default} matching {object_1_layer}")
    index = object_1.GetPrimIndex()
    target_node = index.rootNode.children[1]
    target = Usd.EditTarget(object_1_layer, target_node)
    with Usd.EditContext(main_stage, target):
        bistritz_krone = main_stage.OverridePrim(object_1.GetPath().AppendChild(object_2.GetName()))
        bistritz_krone.GetReferences().AddInternalReference(object_2.GetPath())



if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    import cProfile
    start = datetime.datetime.now()
    pr = cProfile.Profile()
    pr.enable()
    stage = pr.runcall(main)
    pr.disable()
    pr.dump_stats(str(Path(__file__).parent / "stats_no_init_name.log"))
    end = datetime.datetime.now()
    print(f"Total time: {end - start}")