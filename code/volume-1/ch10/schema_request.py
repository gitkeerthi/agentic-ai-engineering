"""Chapter 10 demo: ask the framework for a Finding, and see what the provider does with the schema.

With response_format set to a Pydantic model, the framework sends the model's JSON Schema in the request
(a json_schema response format) and parses the reply into result.value.
"""

import asyncio

from contracts import Finding
from investigate import TASK, investigator

try:
    result = asyncio.run(investigator().run(TASK, options={"response_format": Finding}))  # ①
    print(f"Reply text:\n{result.text}\n")
    print(f"result.value: {result.value!r}")
except Exception as error:
    print(f"The run raised {type(error).__name__}: {error}")
