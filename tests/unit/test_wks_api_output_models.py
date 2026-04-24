from wks.api.config.output_models import output_model, resolve_output_model


def test_output_model_requires_listed_fields() -> None:
    model_class = output_model("UnitOutput", "alpha", "beta")

    instance = model_class(alpha=1, beta=2)

    assert instance.model_dump(mode="python") == {
        "alpha": 1,
        "beta": 2,
        "errors": [],
        "warnings": [],
    }


def test_resolve_output_model_finds_domain_output() -> None:
    resolved = resolve_output_model("config", "list")

    assert resolved is not None
    assert resolved.__name__ == "ConfigListOutput"
