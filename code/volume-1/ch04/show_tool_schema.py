"""Chapter 4 demo: the tool description the framework builds from a Python function. No model call."""

import json

from cobalt import find_document

print(json.dumps(find_document.to_json_schema_spec(), indent=2))
