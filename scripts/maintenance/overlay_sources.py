"""Validate declarations that Compose's resolved config can silently discard."""

from common import MaintenanceError


def validate_source(path, services):
    try:
        import yaml
    except ImportError as error:
        raise MaintenanceError("Compose overlays require PyYAML in the operator's Python runtime") from error

    class StageLoader(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            explicit = set()
            for key, _value in node.value:
                if key.tag == "tag:yaml.org,2002:merge":
                    continue
                name = self.construct_object(key, deep=deep)
                if name in explicit:
                    raise MaintenanceError("Duplicate Compose overlay YAML key")
                explicit.add(name)
            return super().construct_mapping(node, deep=deep)

    def compose_tag(loader, node):
        if node.id == "mapping":
            return loader.construct_mapping(node, deep=True)
        if node.id == "sequence":
            return loader.construct_sequence(node, deep=True)
        return loader.construct_scalar(node)

    for tag in ["!override", "!reset"]:
        StageLoader.add_constructor(tag, compose_tag)
    try:
        source = yaml.load(path.read_text(encoding="utf-8"), Loader=StageLoader)
        if not isinstance(source, dict) or any(
                not isinstance(key, str) or (key != "services" and not key.startswith("x-")) for key in source):
            raise MaintenanceError("Compose overlay source permits only services and inert x- metadata; project/resources/imports refused")
        definitions = source.get("services", {})
        if not isinstance(definitions, dict) or not definitions.keys() <= set(services):
            raise MaintenanceError("Compose overlay source must contain only selected services")
        for definition in definitions.values():
            if not isinstance(definition, dict) or any(key in definition for key in ["extends", "env_file", "label_file"]):
                raise MaintenanceError("Compose overlay indirect source inputs refused; use captured explicit stage fields")
    except (yaml.YAMLError, ValueError, TypeError, RecursionError) as error:
        raise MaintenanceError("Invalid Compose overlay YAML source; details suppressed") from error
