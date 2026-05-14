from manim_skill.llm.catalog import build_component_catalog


def test_catalog_includes_all_registered_components():
    catalog = build_component_catalog()
    for name in [
        "TextBeat", "CodeWalkthrough", "NeuralNetDiagram", "AttentionFlow",
        "MatrixOp", "PlotEvolution", "PipelineDiagram", "GeometryAnim",
        "FormulaBreakdown",
    ]:
        assert name in catalog


def test_catalog_includes_params_schema():
    catalog = build_component_catalog()
    # TextBeat's params model has a "text" field; the JSON schema has
    # a "properties" key.
    assert "text" in catalog
    assert "properties" in catalog


def test_catalog_is_non_empty_string():
    catalog = build_component_catalog()
    assert isinstance(catalog, str)
    assert len(catalog) > 0
