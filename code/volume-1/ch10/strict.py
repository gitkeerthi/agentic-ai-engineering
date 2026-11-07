"""Schema helpers for strict tool definitions on the provider's beta endpoint (Chapter 10).

Strict mode is meant to constrain a tool call's arguments to the tool's JSON Schema as the model writes them;
strict_schema.py tests whether it does. The schema must close every object (additionalProperties: false)
and list every property as required.
"""


def closed(schema):
    """The schema with additionalProperties: false on every object."""
    if isinstance(schema, dict):
        schema = {key: closed(value) for key, value in schema.items()}
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
    elif isinstance(schema, list):
        schema = [closed(item) for item in schema]
    return schema


def inlined(schema, defs=None):
    """The schema with every $ref replaced by the definition it points to, and no $defs."""
    defs = schema.get("$defs", {}) if defs is None else defs
    if isinstance(schema, dict):
        if "$ref" in schema:
            return inlined(defs[schema["$ref"].split("/")[-1]], defs)
        return {key: inlined(value, defs) for key, value in schema.items() if key != "$defs"}
    if isinstance(schema, list):
        return [inlined(item, defs) for item in schema]
    return schema
